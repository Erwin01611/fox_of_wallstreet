"""Backtest pipeline aligned with the modular processor architecture."""

import os
import sys
import json

import joblib
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecFrameStack

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from core.experiment_journal import log_backtest_result
from core.environment import TradingEnv
from core.processor import (
    add_technical_indicators,
    build_news_sentiment,
    load_raw_macro,
    load_raw_news,
    load_raw_prices,
    merge_prices_news_macro,
)


def _resolve_trained_artifact_paths():
    """Resolve model/ledger paths, handling timestamped experiment names across runs."""
    current_model_zip = f"{settings.MODEL_PATH}.zip"
    current_scaler = settings.SCALER_PATH
    current_metadata = settings.METADATA_PATH
    if os.path.exists(current_model_zip) and os.path.exists(current_scaler):
        return (
            settings.MODEL_PATH,
            settings.SCALER_PATH,
            settings.BACKTEST_LEDGER_PATH,
            current_metadata,
        )

    # Fallback: find latest compatible run directory produced by a prior training command.
    prefix = (
        f"ppo_{settings.SYMBOL}_{settings.TIMEFRAME}_{settings.ACTION_SPACE_TYPE}"
        f"_{'news' if settings.USE_NEWS_FEATURES else 'nonews'}"
        f"_{'macro' if settings.USE_MACRO_FEATURES else 'nomacro'}"
        f"_{'time' if settings.USE_TIME_FEATURES else 'notime'}_"
    )

    candidates = []
    for name in os.listdir(settings.ARTIFACTS_BASE_DIR):
        run_dir = os.path.join(settings.ARTIFACTS_BASE_DIR, name)
        model_zip = os.path.join(run_dir, "model.zip")
        scaler_pkl = os.path.join(run_dir, "scaler.pkl")
        if (
            os.path.isdir(run_dir)
            and name.startswith(prefix)
            and os.path.exists(model_zip)
            and os.path.exists(scaler_pkl)
        ):
            candidates.append((os.path.getmtime(model_zip), run_dir))

    if not candidates:
        raise FileNotFoundError(
            f"❌ Trained model not found at {current_model_zip} and no compatible prior run found in "
            f"{settings.ARTIFACTS_BASE_DIR}. Run scripts/train.py first."
        )

    latest_run_dir = sorted(candidates, key=lambda x: x[0], reverse=True)[0][1]
    resolved_model_path = os.path.join(latest_run_dir, "model")
    resolved_scaler_path = os.path.join(latest_run_dir, "scaler.pkl")
    resolved_ledger_path = os.path.join(latest_run_dir, "backtest_ledger.csv")
    resolved_metadata_path = os.path.join(latest_run_dir, "metadata.json")
    print(f"ℹ️ Using latest compatible artifact run: {latest_run_dir}")
    return (
        resolved_model_path,
        resolved_scaler_path,
        resolved_ledger_path,
        resolved_metadata_path,
    )


def _validate_backtest_compatibility(metadata_path):
    """Fail fast when current runtime settings differ from training run settings."""
    if not os.path.exists(metadata_path):
        print(f"⚠️ Metadata file not found at {metadata_path}; skipping compatibility check.")
        return

    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    expected = {
        "symbol": settings.SYMBOL,
        "timeframe": settings.TIMEFRAME,
        "action_space": settings.ACTION_SPACE_TYPE,
        "reward_strategy": settings.REWARD_STRATEGY,
        "n_stack": settings.N_STACK,
        "features_used": settings.FEATURES_LIST,
        "feature_count": settings.EXPECTED_MARKET_FEATURES,
        "use_news": settings.USE_NEWS_FEATURES,
        "use_macro": settings.USE_MACRO_FEATURES,
        "use_time": settings.USE_TIME_FEATURES,
        "cash_risk_fraction": settings.CASH_RISK_FRACTION,
    }

    mismatches = []
    for key, current_value in expected.items():
        trained_value = metadata.get(key)
        if trained_value != current_value:
            mismatches.append((key, trained_value, current_value))

    if mismatches:
        lines = [
            "❌ Backtest compatibility check failed.",
            "Current settings do not match the resolved training run metadata:",
        ]
        for key, trained, current in mismatches:
            lines.append(f"  - {key}: trained={trained} | current={current}")
        lines.append("Align config/settings.py with the trained run, or retrain with current settings.")
        raise ValueError("\n".join(lines))

    print("✅ Backtest compatibility check passed against training metadata.")


def _scale_with_resolved_scaler(df, scaler_path):
    """Scale features using scaler from resolved artifact run."""
    features_list = settings.FEATURES_LIST
    missing = [col for col in features_list if col not in df.columns]
    if missing:
        raise ValueError(f"❌ Missing requested feature columns in test set: {missing}")

    data_to_scale = df[features_list].replace([float("inf"), float("-inf")], pd.NA).fillna(0.0)
    scaler = joblib.load(scaler_path)
    scaled_data = scaler.transform(data_to_scale)
    return pd.DataFrame(scaled_data, columns=features_list, index=df.index)


def _safe_mtime(path):
    return int(os.path.getmtime(path)) if path and os.path.exists(path) else None


def _test_dataset_signature():
    return {
        "symbol": settings.SYMBOL,
        "timeframe": settings.TIMEFRAME,
        "test_start_date": settings.TEST_START_DATE,
        "test_end_date": settings.TEST_END_DATE,
        "features_list": settings.FEATURES_LIST,
        "use_news": settings.USE_NEWS_FEATURES,
        "use_macro": settings.USE_MACRO_FEATURES,
        "use_time": settings.USE_TIME_FEATURES,
        "rsi_window": settings.RSI_WINDOW,
        "macd_fast": settings.MACD_FAST,
        "macd_slow": settings.MACD_SLOW,
        "macd_signal": settings.MACD_SIGNAL,
        "volatility_window": settings.VOLATILITY_WINDOW,
        "news_ema_span": settings.NEWS_EMA_SPAN,
        "raw_prices_mtime": _safe_mtime(settings.RAW_PRICES_CSV),
        "raw_news_mtime": _safe_mtime(settings.RAW_NEWS_CSV),
        "raw_macro_mtime": _safe_mtime(settings.RAW_MACRO_CSV),
    }


def _load_test_checkpoint_if_compatible():
    if not os.path.exists(settings.TEST_FEATURES_CSV):
        return None
    if not os.path.exists(settings.TEST_FEATURES_SIGNATURE_JSON):
        print("⚠️ Test checkpoint signature missing; rebuilding test features.")
        return None

    with open(settings.TEST_FEATURES_SIGNATURE_JSON, "r") as f:
        saved_signature = json.load(f)

    current_signature = _test_dataset_signature()
    if saved_signature != current_signature:
        print("⚠️ Test checkpoint signature mismatch; rebuilding test features.")
        return None

    print("⚡ Loaded test features from compatible checkpoint.")
    return pd.read_csv(settings.TEST_FEATURES_CSV, parse_dates=["Date"])


def _write_test_signature():
    os.makedirs(os.path.dirname(settings.TEST_FEATURES_SIGNATURE_JSON), exist_ok=True)
    with open(settings.TEST_FEATURES_SIGNATURE_JSON, "w") as f:
        json.dump(_test_dataset_signature(), f, indent=2)


def _build_or_load_test_dataset():
    """Load cached test features or build them from raw checkpoints."""
    cached = _load_test_checkpoint_if_compatible()
    if cached is not None:
        return cached

    # Rebuild test features from raw checkpoints using the same processor flow.
    prices_df = load_raw_prices()
    news_df = load_raw_news()
    macro_df = load_raw_macro()
    sentiment_df = build_news_sentiment(news_df, timeframe=settings.TIMEFRAME)
    merged_df = merge_prices_news_macro(prices_df, sentiment_df, macro_df)
    full_feature_df = add_technical_indicators(merged_df)

    test_start = pd.to_datetime(settings.TEST_START_DATE)
    test_end = pd.to_datetime(settings.TEST_END_DATE)
    test_df = full_feature_df[
        (full_feature_df["Date"] >= test_start) &
        (full_feature_df["Date"] <= test_end)
    ].copy().reset_index(drop=True)

    if test_df.empty:
        raise ValueError(
            "❌ Test dataset is empty after processing and date filtering. "
            "Check TEST_START_DATE/TEST_END_DATE and raw checkpoints."
        )

    os.makedirs(os.path.dirname(settings.TEST_FEATURES_CSV), exist_ok=True)
    test_df.to_csv(settings.TEST_FEATURES_CSV, index=False)
    _write_test_signature()
    print(f"✅ Test features checkpoint saved to {settings.TEST_FEATURES_CSV}")
    return test_df


def run_backtest():
    """Run deterministic backtest using the trained model and saved scaler."""
    print(f"🧪 STARTING BACKTEST: {settings.EXPERIMENT_NAME}")

    model_base_path, scaler_path, ledger_path, metadata_path = _resolve_trained_artifact_paths()
    model_path = f"{model_base_path}.zip"
    run_id = os.path.basename(os.path.dirname(model_base_path))

    _validate_backtest_compatibility(metadata_path)

    test_df = _build_or_load_test_dataset()
    print(f"📅 Testing data: {len(test_df)} rows | {settings.TEST_START_DATE} → {settings.TEST_END_DATE}")

    # Use the scaler fitted in the same resolved training run.
    scaled_features = _scale_with_resolved_scaler(test_df, scaler_path)

    base_env = TradingEnv(df=test_df, features=scaled_features)
    vec_env = DummyVecEnv([lambda: base_env])
    env = VecFrameStack(vec_env, n_stack=settings.N_STACK)

    model = PPO.load(model_base_path, env=env)
    print(f"🧠 Loaded trained model from {model_path}")

    obs = env.reset()
    done = False
    trade_history = []
    last_step_info = None

    if settings.ACTION_SPACE_TYPE == "discrete_3":
        action_map = {0: "SELL_ALL", 1: "BUY_ALL", 2: "HOLD"}
    else:
        action_map = {
            0: "SELL_100",
            1: "SELL_50",
            2: "HOLD",
            3: "BUY_50",
            4: "BUY_100",
        }

    prev_position = float(env.get_attr("position")[0])
    print("📈 Simulating deterministic policy...")

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, rewards, dones, infos = env.step(action)
        done = bool(dones[0])
        step_info = infos[0]
        last_step_info = step_info

        actual_action = int(step_info["action"])
        current_position = float(env.get_attr("position")[0])
        sl_tp_triggered = bool(step_info.get("sl_tp_triggered", False))
        position_changed = current_position != prev_position

        # Log explicit trade actions and forced SL/TP exits.
        if sl_tp_triggered or (position_changed and actual_action != 2):
            step_idx = int(step_info["step"])
            if step_idx < 0 or step_idx >= len(test_df):
                continue
            trade_history.append(
                {
                    "Date": test_df.iloc[step_idx]["Date"],
                    "Action": "FORCED_SL_TP" if sl_tp_triggered else action_map.get(actual_action, "UNKNOWN"),
                    "Price": round(float(step_info["price"]), 6),
                    "Portfolio_Value": round(float(step_info["portfolio_value"]), 6),
                    "SL_TP_Triggered": sl_tp_triggered,
                }
            )

        prev_position = current_position

    if last_step_info is None:
        raise RuntimeError("❌ Backtest ended before any environment step was processed.")

    initial_val = float(base_env.initial_balance)
    final_val = float(last_step_info["portfolio_value"])
    total_return = ((final_val - initial_val) / (initial_val + 1e-8)) * 100.0

    print("=" * 60)
    print(f"🏆 BACKTEST RESULTS: {settings.EXPERIMENT_NAME}")
    print(f"Final Portfolio Value: ${final_val:.2f}")
    print(f"Total Return: {total_return:.2f}%")
    print(f"Logged Events: {len(trade_history)}")
    print("=" * 60)

    if trade_history:
        df_trades = pd.DataFrame(trade_history)
        os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
        df_trades.to_csv(ledger_path, index=False)
        print(f"💾 Ledger saved to {ledger_path}")
    else:
        print("ℹ️ No trade events were logged for this backtest run.")

    log_backtest_result(
        run_id=run_id,
        final_portfolio_value=final_val,
        total_return_pct=total_return,
        logged_events=len(trade_history),
        ledger_path=ledger_path,
    )


if __name__ == "__main__":
    run_backtest()
