'''
Place for global things.
'''
import os
import sys
from config import settings

def fnline():
    '''
    For logging and tracing.
    Returns current filename and line number.
    E.g.: backtest.py(144))
    '''
    return os.path.basename(sys.argv[0]) + '(' + str(sys._getframe(1).f_lineno) + '):'

def get_features_list():
    '''
    Return the list of features.
    If time frame is 1 hour return some more.
    '''
    base_features = [
        'Log_Return',
        'Volume_Z_Score',
        'RSI',
        'MACD_Hist',
        'BB_Pct',
        'ATR_Pct',
        'Realized_Vol_Short',
        'Realized_Vol_Long',
        'Vol_Regime',
        'Dist_MA_Fast',
        'Dist_MA_Slow',
        'QQQ_Ret',
        'ARKK_Ret',
        'Rel_Strength_QQQ',
        'VIX_Z',
        'TNX_Z',
        'Sentiment_EMA',
        'News_Intensity'
    ]

    if settings.TIMEFRAME == "1h":
        return base_features + ['Sin_Time', 'Cos_Time', 'Mins_to_Close']
    elif settings.TIMEFRAME == "1d":
        return base_features
    else:
        raise ValueError(f"Unsupported TIMEFRAME: {settings.TIMEFRAME}")

def get_stack_size():
    if settings.TIMEFRAME == "1h":
        return 5
    elif settings.TIMEFRAME == "1d":
        return 10
    else:
        raise ValueError(f"Unsupported TIMEFRAME: {settings.TIMEFRAME}")
