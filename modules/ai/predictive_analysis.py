import pandas as pd
import numpy as np
from typing import Dict, List
import warnings
warnings.filterwarnings('ignore')

try:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import PolynomialFeatures
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.metrics import mean_squared_error
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    LinearRegression = None
    PolynomialFeatures = None
    RandomForestRegressor = None
    GradientBoostingRegressor = None
    mean_squared_error = None

class PredictiveAnalyzer:
    """预测分析模块 — V2.0 (特征工程 + 集成模型)"""

    def __init__(self):
        self.models = {}
        self.prediction_history = []

    # ==================================================================
    # 特征工程
    # ==================================================================
    @staticmethod
    def _build_features(prices: np.ndarray, volumes: np.ndarray = None) -> np.ndarray:
        """
        从收盘价序列构建多维特征矩阵。
        特征: MA5/10/20/60 比率, RSI, MACD柱, 5日波动率, 5日动量, 量比
        """
        n = len(prices)
        feats = np.zeros((n, 10))

        # MA 比率 (当前价 / MA - 1)
        for i, w in enumerate([5, 10, 20, 60]):
            ma = pd.Series(prices).rolling(w, min_periods=1).mean().values
            feats[:, i] = (prices / np.where(ma > 0, ma, 1e-8)) - 1

        # RSI(14)
        delta = np.diff(prices, prepend=prices[0])
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = pd.Series(gain).rolling(14, min_periods=1).mean().values
        avg_loss = pd.Series(loss).rolling(14, min_periods=1).mean().values
        rs = avg_gain / np.where(avg_loss > 0, avg_loss, 1e-8)
        feats[:, 4] = (100 - 100 / (1 + rs)) / 100  # 归一化到 0~1

        # MACD 柱
        ema12 = pd.Series(prices).ewm(span=12, adjust=False).mean().values
        ema26 = pd.Series(prices).ewm(span=26, adjust=False).mean().values
        macd = ema12 - ema26
        signal = pd.Series(macd).ewm(span=9, adjust=False).mean().values
        price_std = np.std(prices) if np.std(prices) > 0 else 1
        feats[:, 5] = (macd - signal) / price_std  # 标准化

        # 5日波动率
        ret = np.diff(prices, prepend=prices[0]) / np.where(prices > 0, prices, 1e-8)
        feats[:, 6] = pd.Series(ret).rolling(5, min_periods=1).std().values

        # 5日动量 (change %)
        feats[5:, 7] = (prices[5:] - prices[:-5]) / np.where(prices[:-5] > 0, prices[:-5], 1e-8)

        # 20日动量
        feats[20:, 8] = (prices[20:] - prices[:-20]) / np.where(prices[:-20] > 0, prices[:-20], 1e-8)

        # 量比 (volume / MA5_volume)
        if volumes is not None and len(volumes) == n:
            vol_ma5 = pd.Series(volumes).rolling(5, min_periods=1).mean().values
            feats[:, 9] = volumes / np.where(vol_ma5 > 0, vol_ma5, 1e-8)
        else:
            feats[:, 9] = 1.0

        return feats

    # ==================================================================
    # 简单线性预测 (无 sklearn 后备)
    # ==================================================================
    def _simple_linear_predict(self, prices: np.ndarray, days: int) -> np.ndarray:
        """简单线性预测（无需sklearn）"""
        n = len(prices)
        x = np.arange(n)
        slope = (n * np.sum(x * prices) - np.sum(x) * np.sum(prices)) / (n * np.sum(x**2) - np.sum(x)**2)
        intercept = (np.sum(prices) - slope * np.sum(x)) / n
        future_x = np.arange(n, n + days)
        return slope * future_x + intercept

    # ==================================================================
    # 核心预测方法
    # ==================================================================
    def trend_prediction(self, df: pd.DataFrame, days: int = 5, method: str = 'linear') -> Dict:
        """
        趋势预测 — V2.0

        使用特征工程 + 滚动预测方式生成未来 N 天价格序列。
        - linear: 线性回归，基于多维技术特征
        - poly:   二次多项式回归
        - rf:     随机森林（特征重要性 + 滚动推进）
        - gbdt:   梯度提升决策树（新增）
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
            vol_col = 'volume' if 'volume' in df.columns else '成交量'
            prices = df[close_col].astype(float).values
            volumes = df[vol_col].astype(float).values if vol_col in df.columns else None

            if not SKLEARN_AVAILABLE:
                predictions = self._simple_linear_predict(prices, days)
                trend = 'up' if predictions[-1] > prices[-1] else 'down'
                return {
                    'predictions': predictions.tolist(),
                    'current_price': float(prices[-1]),
                    'predicted_price': float(predictions[-1]),
                    'expected_change': float((predictions[-1] - prices[-1]) / prices[-1] * 100),
                    'trend': trend,
                    'confidence': 50.0,
                    'method': 'simple_linear'
                }

            # ---- 特征构建 ----
            features = self._build_features(prices, volumes)

            # 目标: 未来 1 日收益率
            target = np.zeros(len(prices))
            target[:-1] = (prices[1:] - prices[:-1]) / np.where(prices[:-1] > 0, prices[:-1], 1e-8)

            # 训练集 (去掉前60天warm-up和最后1天target缺失)
            warmup = 60
            X_train = features[warmup:-1]
            y_train = target[warmup:-1]

            if len(X_train) < 20:
                predictions = self._simple_linear_predict(prices, days)
                return {
                    'predictions': predictions.tolist(),
                    'current_price': float(prices[-1]),
                    'predicted_price': float(predictions[-1]),
                    'expected_change': float((predictions[-1] - prices[-1]) / prices[-1] * 100),
                    'trend': 'up' if predictions[-1] > prices[-1] else 'down',
                    'confidence': 40.0,
                    'method': method
                }

            # ---- 选择模型 ----
            if method == 'poly':
                poly = PolynomialFeatures(degree=2, interaction_only=True, include_bias=False)
                X_poly = poly.fit_transform(X_train)
                model = LinearRegression()
                model.fit(X_poly, y_train)
            elif method == 'rf':
                model = RandomForestRegressor(
                    n_estimators=200, max_depth=6,
                    min_samples_leaf=5, random_state=42, n_jobs=-1
                )
                model.fit(X_train, y_train)
            elif method == 'gbdt':
                model = GradientBoostingRegressor(
                    n_estimators=150, max_depth=4,
                    learning_rate=0.05, subsample=0.8, random_state=42
                )
                model.fit(X_train, y_train)
            else:  # linear
                model = LinearRegression()
                model.fit(X_train, y_train)

            # ---- 滚动推进预测 ----
            predicted_prices = [float(prices[-1])]
            current_prices = list(prices)
            current_volumes = list(volumes) if volumes is not None else None

            for _ in range(days):
                arr_p = np.array(current_prices)
                arr_v = np.array(current_volumes) if current_volumes is not None else None
                feat = self._build_features(arr_p, arr_v)
                latest_feat = feat[-1:, :]

                if method == 'poly':
                    latest_feat = poly.transform(latest_feat)

                pred_return = model.predict(latest_feat)[0]

                # 限制单日预测振幅 (±5%), 避免极端值
                pred_return = np.clip(pred_return, -0.05, 0.05)

                next_price = predicted_prices[-1] * (1 + pred_return)
                predicted_prices.append(float(next_price))
                current_prices.append(float(next_price))
                if current_volumes is not None:
                    # 成交量用最近5日均量作为代理
                    current_volumes.append(float(np.mean(current_volumes[-5:])))

            predictions = predicted_prices[1:]  # 去掉当前价

            # ---- 模型评估 (真正的 Walk-Forward, 不用训练数据) ----
            split = max(int(len(X_train) * 0.8), 10)
            if split < len(X_train) - 2:
                X_tr_eval = X_train[:split]
                y_tr_eval = y_train[:split]
                X_val = X_train[split:]
                y_val = y_train[split:]

                # 用前80%数据单独训练一个评估模型
                if method == 'poly':
                    poly_eval = PolynomialFeatures(degree=2, interaction_only=True, include_bias=False)
                    X_tr_eval_t = poly_eval.fit_transform(X_tr_eval)
                    eval_model = LinearRegression()
                    eval_model.fit(X_tr_eval_t, y_tr_eval)
                    X_val_t = poly_eval.transform(X_val)
                elif method == 'rf':
                    eval_model = RandomForestRegressor(
                        n_estimators=200, max_depth=6,
                        min_samples_leaf=5, random_state=42, n_jobs=-1)
                    eval_model.fit(X_tr_eval, y_tr_eval)
                    X_val_t = X_val
                elif method == 'gbdt':
                    eval_model = GradientBoostingRegressor(
                        n_estimators=150, max_depth=4,
                        learning_rate=0.05, subsample=0.8, random_state=42)
                    eval_model.fit(X_tr_eval, y_tr_eval)
                    X_val_t = X_val
                else:
                    eval_model = LinearRegression()
                    eval_model.fit(X_tr_eval, y_tr_eval)
                    X_val_t = X_val

                y_pred_val = eval_model.predict(X_val_t)

                # 过滤掉 y_val ≈ 0 的样本 (涨跌幅 < 0.1% 视为噪声)
                mask = np.abs(y_val) > 0.001
                if mask.sum() > 5:
                    direction_correct = float(np.mean(
                        np.sign(y_pred_val[mask]) == np.sign(y_val[mask])))
                else:
                    direction_correct = float(np.mean(
                        np.sign(y_pred_val) == np.sign(y_val)))

                # 相关系数
                if np.std(y_val) > 0 and np.std(y_pred_val) > 0:
                    corr = float(np.corrcoef(y_val, y_pred_val)[0, 1])
                    corr = max(corr, 0)
                else:
                    corr = 0.0
            else:
                direction_correct = 0.5
                corr = 0.0

            # 综合置信度: 方向准确率 * 0.6 + 相关系数 * 0.4, 上限 85%
            confidence = min((direction_correct * 0.6 + corr * 0.4) * 100, 85)
            confidence = max(confidence, 25)  # 下限 25%

            trend = 'up' if predictions[-1] > prices[-1] else 'down'

            return {
                'predictions': predictions,
                'current_price': float(prices[-1]),
                'predicted_price': float(predictions[-1]),
                'expected_change': float((predictions[-1] - prices[-1]) / prices[-1] * 100),
                'trend': trend,
                'confidence': round(confidence, 1),
                'method': method,
                'direction_accuracy': round(direction_correct * 100, 1),
            }

        except Exception as e:
            return {
                'predictions': [],
                'trend': 'unknown',
                'confidence': 0.0,
                'error': str(e)
            }

    def risk_assessment(self, df: pd.DataFrame) -> Dict:
        """风险评估"""
        if df.empty or len(df) < 20:
            return {
                'risk_level': 'unknown',
                'risk_score': 0,
                'error': '数据不足'
            }

        try:
            close_col = 'close' if 'close' in df.columns else '收盘'
            prices = df[close_col]

            returns = prices.pct_change().dropna()
            volatility = returns.std() * np.sqrt(252) * 100
            cummax = prices.cummax()
            drawdown = (prices - cummax) / cummax
            max_drawdown = drawdown.min() * 100
            downside_returns = returns[returns < 0]
            downside_risk = downside_returns.std() * np.sqrt(252) * 100 if len(downside_returns) > 0 else 0
            var_95 = np.percentile(returns, 5) * 100

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
        """计算支撑阻力位"""
        if df.empty or len(df) < window:
            return {'error': '数据不足'}

        try:
            high_col = 'high' if 'high' in df.columns else '最高'
            low_col = 'low' if 'low' in df.columns else '最低'
            close_col = 'close' if 'close' in df.columns else '收盘'

            recent_data = df.tail(window)
            recent_highs = recent_data[high_col].nlargest(3).values
            recent_lows = recent_data[low_col].nsmallest(3).values

            resistance = np.mean(recent_highs)
            support = np.mean(recent_lows)
            current_price = df[close_col].iloc[-1]

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
        """动量分析"""
        if df.empty or len(df) < 60:
            return {'error': '数据不足'}

        try:
            close_col = 'close' if 'close' in df.columns else '收盘'
            prices = df[close_col]

            returns_1d = (prices.iloc[-1] / prices.iloc[-2] - 1) * 100
            returns_5d = (prices.iloc[-1] / prices.iloc[-6] - 1) * 100 if len(prices) >= 6 else 0
            returns_20d = (prices.iloc[-1] / prices.iloc[-21] - 1) * 100 if len(prices) >= 21 else 0
            returns_60d = (prices.iloc[-1] / prices.iloc[-61] - 1) * 100 if len(prices) >= 61 else 0

            momentum_score = 0
            if returns_1d > 0:
                momentum_score += 10
            if returns_5d > 0:
                momentum_score += 20
            if returns_20d > 0:
                momentum_score += 30
            if returns_60d > 0:
                momentum_score += 40

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
        """预测价格区间"""
        if df.empty or len(df) < 30:
            return {'error': '数据不足'}

        try:
            close_col = 'close' if 'close' in df.columns else '收盘'
            prices = df[close_col].values

            returns = np.diff(prices) / prices[:-1]
            volatility = np.std(returns)

            # 使用特征工程预测中心价
            result = self.trend_prediction(df, days, method='rf')
            if result.get('predictions'):
                predicted_price = result['predicted_price']
            else:
                X = np.arange(len(prices)).reshape(-1, 1)
                model = LinearRegression()
                model.fit(X, prices)
                future_X = np.arange(len(prices), len(prices) + days).reshape(-1, 1)
                predicted_price = model.predict(future_X)[-1]

            z_score = 1.96 if confidence == 0.95 else 2.58
            margin = z_score * volatility * np.sqrt(days) * predicted_price

            return {
                'predicted_price': round(float(predicted_price), 2),
                'lower_bound': round(max(float(predicted_price - margin), 0), 2),
                'upper_bound': round(float(predicted_price + margin), 2),
                'confidence': confidence * 100,
                'days': days
            }

        except Exception as e:
            return {'error': str(e)}
