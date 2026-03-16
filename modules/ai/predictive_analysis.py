import pandas as pd
import numpy as np
from typing import Dict, List
import warnings
warnings.filterwarnings('ignore')

try:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import PolynomialFeatures
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_squared_error
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    LinearRegression = None
    PolynomialFeatures = None
    RandomForestRegressor = None
    mean_squared_error = None

class PredictiveAnalyzer:
    """预测分析模块"""
    
    def __init__(self):
        self.models = {}
        self.prediction_history = []
    
    def _simple_linear_predict(self, prices: np.ndarray, days: int) -> np.ndarray:
        """简单线性预测（无需sklearn）"""
        n = len(prices)
        x = np.arange(n)
        # 最小二乘法计算斜率和截距
        slope = (n * np.sum(x * prices) - np.sum(x) * np.sum(prices)) / (n * np.sum(x**2) - np.sum(x)**2)
        intercept = (np.sum(prices) - slope * np.sum(x)) / n
        # 预测未来值
        future_x = np.arange(n, n + days)
        return slope * future_x + intercept
    
    def trend_prediction(self, df: pd.DataFrame, days: int = 5, method: str = 'linear') -> Dict:
        """
        趋势预测
        
        Args:
            df: 包含价格数据的DataFrame
            days: 预测天数
            method: 预测方法 ('linear', 'poly', 'rf')
        
        Returns:
            预测结果字典
        """
        if df.empty or len(df) < 30:
            return {
                'predictions': [],
                'trend': 'unknown',
                'confidence': 0.0,
                'error': '数据不足'
            }
        
        try:
            close_col = 'close' if 'close' in df.columns else '收盘'
            prices = df[close_col].values
            
            # 如果没有sklearn，使用简单线性预测
            if not SKLEARN_AVAILABLE:
                predictions = self._simple_linear_predict(prices, days)
                trend = 'up' if predictions[-1] > prices[-1] else 'down'
                return {
                    'predictions': predictions.tolist(),
                    'current_price': prices[-1],
                    'predicted_price': predictions[-1],
                    'expected_change': (predictions[-1] - prices[-1]) / prices[-1] * 100,
                    'trend': trend,
                    'confidence': 50.0,  # 基础置信度
                    'method': 'simple_linear'
                }
            
            X = np.arange(len(prices)).reshape(-1, 1)
            y = prices
            
            if method == 'poly':
                # 多项式回归
                poly = PolynomialFeatures(degree=2)
                X_poly = poly.fit_transform(X)
                model = LinearRegression()
                model.fit(X_poly, y)
                
                future_X = np.arange(len(prices), len(prices) + days).reshape(-1, 1)
                future_X_poly = poly.transform(future_X)
                predictions = model.predict(future_X_poly)
                
            elif method == 'rf':
                # 随机森林
                model = RandomForestRegressor(n_estimators=100, random_state=42)
                model.fit(X, y)
                
                future_X = np.arange(len(prices), len(prices) + days).reshape(-1, 1)
                predictions = model.predict(future_X)
                
            else:
                # 线性回归
                model = LinearRegression()
                model.fit(X, y)
                
                future_X = np.arange(len(prices), len(prices) + days).reshape(-1, 1)
                predictions = model.predict(future_X)
            
            # 计算置信度（基于历史拟合度）
            y_pred = model.predict(X_poly if method == 'poly' else X)
            mse = mean_squared_error(y, y_pred)
            confidence = max(0, 1 - mse / np.var(y)) if np.var(y) > 0 else 0
            
            # 判断趋势
            trend = 'up' if predictions[-1] > prices[-1] else 'down'
            
            return {
                'predictions': predictions.tolist(),
                'current_price': prices[-1],
                'predicted_price': predictions[-1],
                'expected_change': (predictions[-1] - prices[-1]) / prices[-1] * 100,
                'trend': trend,
                'confidence': min(confidence * 100, 95),
                'method': method
            }
            
        except Exception as e:
            return {
                'predictions': [],
                'trend': 'unknown',
                'confidence': 0.0,
                'error': str(e)
            }
    
    def risk_assessment(self, df: pd.DataFrame) -> Dict:
        """
        风险评估
        
        Args:
            df: 包含价格数据的DataFrame
        
        Returns:
            风险评估结果
        """
        if df.empty or len(df) < 20:
            return {
                'risk_level': 'unknown',
                'risk_score': 0,
                'error': '数据不足'
            }
        
        try:
            close_col = 'close' if 'close' in df.columns else '收盘'
            prices = df[close_col]
            
            # 计算收益率
            returns = prices.pct_change().dropna()
            
            # 年化波动率
            volatility = returns.std() * np.sqrt(252) * 100
            
            # 最大回撤
            cummax = prices.cummax()
            drawdown = (prices - cummax) / cummax
            max_drawdown = drawdown.min() * 100
            
            # 下行风险（下行标准差）
            downside_returns = returns[returns < 0]
            downside_risk = downside_returns.std() * np.sqrt(252) * 100 if len(downside_returns) > 0 else 0
            
            # VaR (Value at Risk) 95%
            var_95 = np.percentile(returns, 5) * 100
            
            # 计算风险评分 (0-100)
            risk_score = 0
            if volatility > 30:
                risk_score += 30
            elif volatility > 20:
                risk_score += 20
            else:
                risk_score += 10
            
            if max_drawdown < -30:
                risk_score += 35
            elif max_drawdown < -20:
                risk_score += 25
            else:
                risk_score += 15
            
            if downside_risk > 25:
                risk_score += 20
            elif downside_risk > 15:
                risk_score += 10
            
            if abs(var_95) > 5:
                risk_score += 15
            
            # 风险等级
            if risk_score >= 70:
                risk_level = 'High'
            elif risk_score >= 40:
                risk_level = 'Medium'
            else:
                risk_level = 'Low'
            
            return {
                'volatility': round(volatility, 2),
                'max_drawdown': round(max_drawdown, 2),
                'downside_risk': round(downside_risk, 2),
                'var_95': round(var_95, 2),
                'risk_score': risk_score,
                'risk_level': risk_level
            }
            
        except Exception as e:
            return {
                'risk_level': 'unknown',
                'risk_score': 0,
                'error': str(e)
            }
    
    def support_resistance(self, df: pd.DataFrame, window: int = 20) -> Dict:
        """
        计算支撑阻力位
        
        Args:
            df: 包含价格数据的DataFrame
            window: 计算窗口
        
        Returns:
            支撑阻力位
        """
        if df.empty or len(df) < window:
            return {'error': '数据不足'}
        
        try:
            high_col = 'high' if 'high' in df.columns else '最高'
            low_col = 'low' if 'low' in df.columns else '最低'
            close_col = 'close' if 'close' in df.columns else '收盘'
            
            recent_data = df.tail(window)
            
            # 近期高点和低点
            recent_highs = recent_data[high_col].nlargest(3).values
            recent_lows = recent_data[low_col].nsmallest(3).values
            
            # 计算支撑位和阻力位
            resistance = np.mean(recent_highs)
            support = np.mean(recent_lows)
            current_price = df[close_col].iloc[-1]
            
            # 计算斐波那契回撤位
            price_range = resistance - support
            fib_382 = resistance - price_range * 0.382
            fib_500 = resistance - price_range * 0.5
            fib_618 = resistance - price_range * 0.618
            
            return {
                'current_price': round(current_price, 2),
                'resistance': round(resistance, 2),
                'support': round(support, 2),
                'fib_382': round(fib_382, 2),
                'fib_500': round(fib_500, 2),
                'fib_618': round(fib_618, 2),
                'position': 'above_support' if current_price > support else 'below_support'
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def momentum_analysis(self, df: pd.DataFrame) -> Dict:
        """
        动量分析
        
        Args:
            df: 包含价格数据的DataFrame
        
        Returns:
            动量分析结果
        """
        if df.empty or len(df) < 60:
            return {'error': '数据不足'}
        
        try:
            close_col = 'close' if 'close' in df.columns else '收盘'
            prices = df[close_col]
            
            # 计算不同周期的收益率
            returns_1d = (prices.iloc[-1] / prices.iloc[-2] - 1) * 100
            returns_5d = (prices.iloc[-1] / prices.iloc[-6] - 1) * 100 if len(prices) >= 6 else 0
            returns_20d = (prices.iloc[-1] / prices.iloc[-21] - 1) * 100 if len(prices) >= 21 else 0
            returns_60d = (prices.iloc[-1] / prices.iloc[-61] - 1) * 100 if len(prices) >= 61 else 0
            
            # 计算动量得分
            momentum_score = 0
            if returns_1d > 0:
                momentum_score += 10
            if returns_5d > 0:
                momentum_score += 20
            if returns_20d > 0:
                momentum_score += 30
            if returns_60d > 0:
                momentum_score += 40
            
            # 动量方向
            if momentum_score >= 70:
                momentum_direction = 'Strong Bullish'
            elif momentum_score >= 50:
                momentum_direction = 'Bullish'
            elif momentum_score >= 30:
                momentum_direction = 'Neutral'
            elif momentum_score >= 10:
                momentum_direction = 'Bearish'
            else:
                momentum_direction = 'Strong Bearish'
            
            return {
                'returns_1d': round(returns_1d, 2),
                'returns_5d': round(returns_5d, 2),
                'returns_20d': round(returns_20d, 2),
                'returns_60d': round(returns_60d, 2),
                'momentum_score': momentum_score,
                'momentum_direction': momentum_direction
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def predict_price_range(self, df: pd.DataFrame, days: int = 5, confidence: float = 0.95) -> Dict:
        """
        预测价格区间
        
        Args:
            df: 包含价格数据的DataFrame
            days: 预测天数
            confidence: 置信水平
        
        Returns:
            价格区间预测
        """
        if df.empty or len(df) < 30:
            return {'error': '数据不足'}
        
        try:
            close_col = 'close' if 'close' in df.columns else '收盘'
            prices = df[close_col].values
            
            # 计算历史波动率
            returns = np.diff(prices) / prices[:-1]
            volatility = np.std(returns)
            
            # 简单趋势预测
            X = np.arange(len(prices)).reshape(-1, 1)
            model = LinearRegression()
            model.fit(X, prices)
            
            # 预测未来价格
            future_X = np.arange(len(prices), len(prices) + days).reshape(-1, 1)
            predicted_price = model.predict(future_X)[-1]
            
            # 计算置信区间
            z_score = 1.96 if confidence == 0.95 else 2.58  # 95% or 99%
            margin = z_score * volatility * np.sqrt(days) * predicted_price
            
            return {
                'predicted_price': round(predicted_price, 2),
                'lower_bound': round(max(predicted_price - margin, 0), 2),
                'upper_bound': round(predicted_price + margin, 2),
                'confidence': confidence * 100,
                'days': days
            }
            
        except Exception as e:
            return {'error': str(e)}
