from enum import Enum
import os
import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

class AIModel(Enum):
    GPT4 = "gpt-4"
    GPT4_TURBO = "gpt-4-turbo"
    CLAUDE = "claude-3"
    CLAUDE_SONNET = "claude-3-sonnet"
    CLAUDE_OPUS = "claude-3-opus"
    GEMINI = "gemini"
    GEMINI_PRO = "gemini-pro"
    KIMI = "kimi"
    KIMI_8K = "kimi-8k"
    KIMI_32K = "kimi-32k"
    DEEPSEEK = "deepseek"
    DEEPSEEK_CHAT = "deepseek-chat"
    DEEPSEEK_CODER = "deepseek-coder"

@dataclass
class ModelPerformance:
    """模型性能指标"""
    model: AIModel
    latency_ms: float
    tokens_used: int
    success: bool
    error_message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    api_key_env: str
    base_url: str = ""
    model_id: str = ""
    max_tokens: int = 2000
    temperature: float = 0.7
    timeout: int = 30
    retry_count: int = 3
    priority: int = 1  # 优先级，数字越小优先级越高

class MultiModelAI:
    """多模型AI管理器 - 增强版"""
    
    # 模型配置映射
    MODEL_CONFIGS = {
        AIModel.GPT4: ModelConfig(
            name="GPT-4",
            api_key_env="OPENAI_API_KEY",
            model_id="gpt-4",
            max_tokens=2000,
            priority=1
        ),
        AIModel.GPT4_TURBO: ModelConfig(
            name="GPT-4 Turbo",
            api_key_env="OPENAI_API_KEY",
            model_id="gpt-4-turbo-preview",
            max_tokens=4000,
            priority=1
        ),
        AIModel.CLAUDE: ModelConfig(
            name="Claude 3",
            api_key_env="ANTHROPIC_API_KEY",
            model_id="claude-3-sonnet-20240229",
            max_tokens=2000,
            priority=2
        ),
        AIModel.CLAUDE_SONNET: ModelConfig(
            name="Claude 3 Sonnet",
            api_key_env="ANTHROPIC_API_KEY",
            model_id="claude-3-sonnet-20240229",
            max_tokens=2000,
            priority=2
        ),
        AIModel.CLAUDE_OPUS: ModelConfig(
            name="Claude 3 Opus",
            api_key_env="ANTHROPIC_API_KEY",
            model_id="claude-3-opus-20240229",
            max_tokens=4000,
            priority=1
        ),
        AIModel.GEMINI: ModelConfig(
            name="Gemini",
            api_key_env="GEMINI_API_KEY",
            model_id="gemini-pro",
            max_tokens=2000,
            priority=3
        ),
        AIModel.GEMINI_PRO: ModelConfig(
            name="Gemini Pro",
            api_key_env="GEMINI_API_KEY",
            model_id="gemini-pro",
            max_tokens=4000,
            priority=2
        ),
        AIModel.KIMI: ModelConfig(
            name="Kimi",
            api_key_env="KIMI_API_KEY",
            base_url="https://api.moonshot.cn/v1",
            model_id="moonshot-v1-8k",
            max_tokens=2000,
            priority=3
        ),
        AIModel.KIMI_8K: ModelConfig(
            name="Kimi 8K",
            api_key_env="KIMI_API_KEY",
            base_url="https://api.moonshot.cn/v1",
            model_id="moonshot-v1-8k",
            max_tokens=2000,
            priority=3
        ),
        AIModel.KIMI_32K: ModelConfig(
            name="Kimi 32K",
            api_key_env="KIMI_API_KEY",
            base_url="https://api.moonshot.cn/v1",
            model_id="moonshot-v1-32k",
            max_tokens=8000,
            priority=2
        ),
        AIModel.DEEPSEEK: ModelConfig(
            name="DeepSeek",
            api_key_env="DEEPSEEK_API_KEY",
            base_url="https://api.deepseek.com/v1",
            model_id="deepseek-chat",
            max_tokens=2000,
            priority=3
        ),
        AIModel.DEEPSEEK_CHAT: ModelConfig(
            name="DeepSeek Chat",
            api_key_env="DEEPSEEK_API_KEY",
            base_url="https://api.deepseek.com/v1",
            model_id="deepseek-chat",
            max_tokens=2000,
            priority=3
        ),
        AIModel.DEEPSEEK_CODER: ModelConfig(
            name="DeepSeek Coder",
            api_key_env="DEEPSEEK_API_KEY",
            base_url="https://api.deepseek.com/v1",
            model_id="deepseek-coder",
            max_tokens=4000,
            priority=2
        ),
    }
    
    def __init__(self, default_model: AIModel = None, auto_fallback: bool = True):
        """
        初始化多模型AI管理器
        
        Args:
            default_model: 默认使用的模型
            auto_fallback: 是否启用自动故障切换
        """
        self.available_models: Dict[AIModel, bool] = {}
        self.current_model = default_model or AIModel.GEMINI
        self.auto_fallback = auto_fallback
        self.performance_history: List[ModelPerformance] = []
        self.max_history_size = 100
        
        self._init_models()
    
    def _init_models(self):
        """初始化所有可用的模型"""
        for model in AIModel:
            config = self.MODEL_CONFIGS.get(model)
            if config:
                api_key = os.getenv(config.api_key_env)
                self.available_models[model] = bool(api_key)
        
        # 如果当前模型不可用，切换到第一个可用模型
        if not self.available_models.get(self.current_model, False):
            for model, available in self.available_models.items():
                if available:
                    self.current_model = model
                    break
    
    def set_model(self, model: AIModel) -> bool:
        """
        设置当前使用的模型
        
        Args:
            model: 要设置的模型
            
        Returns:
            是否设置成功
        """
        if self.available_models.get(model, False):
            self.current_model = model
            return True
        else:
            raise ValueError(f"模型 {model.value} 未配置或不可用，请先设置API密钥")
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        获取所有可用模型列表
        
        Returns:
            可用模型信息列表
        """
        result = []
        for model, available in self.available_models.items():
            config = self.MODEL_CONFIGS.get(model)
            if config:
                result.append({
                    'id': model.value,
                    'name': config.name,
                    'available': available,
                    'priority': config.priority,
                    'max_tokens': config.max_tokens
                })
        # 按优先级排序
        result.sort(key=lambda x: x['priority'])
        return result
    
    def get_model_performance_stats(self) -> Dict[str, Any]:
        """
        获取模型性能统计
        
        Returns:
            性能统计信息
        """
        if not self.performance_history:
            return {}
        
        stats = {}
        for model in AIModel:
            model_history = [p for p in self.performance_history if p.model == model]
            if model_history:
                latencies = [p.latency_ms for p in model_history if p.success]
                success_count = sum(1 for p in model_history if p.success)
                
                stats[model.value] = {
                    'avg_latency_ms': sum(latencies) / len(latencies) if latencies else 0,
                    'success_rate': success_count / len(model_history) * 100,
                    'total_calls': len(model_history),
                    'avg_tokens': sum(p.tokens_used for p in model_history) / len(model_history)
                }
        
        return stats
    
    def _record_performance(self, performance: ModelPerformance):
        """记录模型性能"""
        self.performance_history.append(performance)
        if len(self.performance_history) > self.max_history_size:
            self.performance_history = self.performance_history[-self.max_history_size:]
    
    def generate_response(self, prompt: str, system_prompt: str = None, 
                         model: AIModel = None, temperature: float = None) -> str:
        """
        生成AI响应
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            model: 指定模型（默认使用当前模型）
            temperature: 温度参数
            
        Returns:
            AI响应文本
        """
        target_model = model or self.current_model
        config = self.MODEL_CONFIGS.get(target_model)
        
        if not config:
            return f"未知模型: {target_model.value}"
        
        if not self.available_models.get(target_model, False):
            if self.auto_fallback:
                return self._fallback_generate(prompt, system_prompt, temperature)
            else:
                return f"模型 {config.name} 未配置，请设置 {config.api_key_env} 环境变量"
        
        start_time = time.time()
        tokens_used = 0
        
        try:
            if target_model in [AIModel.GPT4, AIModel.GPT4_TURBO]:
                result = self._call_openai(prompt, system_prompt, config, temperature)
            elif target_model in [AIModel.CLAUDE, AIModel.CLAUDE_SONNET, AIModel.CLAUDE_OPUS]:
                result = self._call_anthropic(prompt, system_prompt, config, temperature)
            elif target_model in [AIModel.GEMINI, AIModel.GEMINI_PRO]:
                result = self._call_gemini(prompt, system_prompt, config, temperature)
            elif target_model in [AIModel.KIMI, AIModel.KIMI_8K, AIModel.KIMI_32K]:
                result = self._call_kimi(prompt, system_prompt, config, temperature)
            elif target_model in [AIModel.DEEPSEEK, AIModel.DEEPSEEK_CHAT, AIModel.DEEPSEEK_CODER]:
                result = self._call_deepseek(prompt, system_prompt, config, temperature)
            else:
                result = "未支持的模型类型"
            
            latency = (time.time() - start_time) * 1000
            self._record_performance(ModelPerformance(
                model=target_model,
                latency_ms=latency,
                tokens_used=len(prompt) + len(result),  # 估算token数
                success=True
            ))
            
            return result
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self._record_performance(ModelPerformance(
                model=target_model,
                latency_ms=latency,
                tokens_used=0,
                success=False,
                error_message=str(e)
            ))
            
            if self.auto_fallback:
                return self._fallback_generate(prompt, system_prompt, temperature, exclude=[target_model])
            else:
                return f"AI调用失败: {str(e)}"
    
    def _fallback_generate(self, prompt: str, system_prompt: str = None, 
                          temperature: float = None, exclude: List[AIModel] = None) -> str:
        """
        故障切换 - 尝试其他可用模型
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度参数
            exclude: 排除的模型列表
            
        Returns:
            AI响应文本
        """
        exclude = exclude or []
        
        # 按优先级排序获取可用模型
        available = [
            (model, self.MODEL_CONFIGS[model].priority)
            for model, is_available in self.available_models.items()
            if is_available and model not in exclude
        ]
        available.sort(key=lambda x: x[1])
        
        for model, _ in available:
            try:
                config = self.MODEL_CONFIGS[model]
                
                if model in [AIModel.GPT4, AIModel.GPT4_TURBO]:
                    return self._call_openai(prompt, system_prompt, config, temperature)
                elif model in [AIModel.CLAUDE, AIModel.CLAUDE_SONNET, AIModel.CLAUDE_OPUS]:
                    return self._call_anthropic(prompt, system_prompt, config, temperature)
                elif model in [AIModel.GEMINI, AIModel.GEMINI_PRO]:
                    return self._call_gemini(prompt, system_prompt, config, temperature)
                elif model in [AIModel.KIMI, AIModel.KIMI_8K, AIModel.KIMI_32K]:
                    return self._call_kimi(prompt, system_prompt, config, temperature)
                elif model in [AIModel.DEEPSEEK, AIModel.DEEPSEEK_CHAT, AIModel.DEEPSEEK_CODER]:
                    return self._call_deepseek(prompt, system_prompt, config, temperature)
                    
            except Exception as e:
                continue
        
        return "所有AI模型均不可用，请检查API密钥配置"
    
    def _call_openai(self, prompt: str, system_prompt: str, config: ModelConfig, 
                     temperature: float = None) -> str:
        """调用OpenAI API"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv(config.api_key_env))
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=config.model_id,
                messages=messages,
                temperature=temperature or config.temperature,
                max_tokens=config.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI调用失败: {str(e)}")
    
    def _call_anthropic(self, prompt: str, system_prompt: str, config: ModelConfig,
                        temperature: float = None) -> str:
        """调用Anthropic Claude API"""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv(config.api_key_env))
            
            message = client.messages.create(
                model=config.model_id,
                max_tokens=config.max_tokens,
                temperature=temperature or config.temperature,
                system=system_prompt or "",
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            raise Exception(f"Claude调用失败: {str(e)}")
    
    def _call_gemini(self, prompt: str, system_prompt: str, config: ModelConfig,
                     temperature: float = None) -> str:
        """调用Google Gemini API"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=os.getenv(config.api_key_env))
            
            model = genai.GenerativeModel(config.model_id)
            
            generation_config = genai.GenerationConfig(
                temperature=temperature or config.temperature,
                max_output_tokens=config.max_tokens
            )
            
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = model.generate_content(full_prompt, generation_config=generation_config)
            
            if response.parts:
                return response.text
            else:
                return "Gemini无法生成响应"
        except Exception as e:
            raise Exception(f"Gemini调用失败: {str(e)}")
    
    def _call_kimi(self, prompt: str, system_prompt: str, config: ModelConfig,
                   temperature: float = None) -> str:
        """调用Moonshot Kimi API"""
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=os.getenv(config.api_key_env),
                base_url=config.base_url
            )
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=config.model_id,
                messages=messages,
                temperature=temperature or config.temperature,
                max_tokens=config.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Kimi调用失败: {str(e)}")
    
    def _call_deepseek(self, prompt: str, system_prompt: str, config: ModelConfig,
                       temperature: float = None) -> str:
        """调用DeepSeek API"""
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=os.getenv(config.api_key_env),
                base_url=config.base_url
            )
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=config.model_id,
                messages=messages,
                temperature=temperature or config.temperature,
                max_tokens=config.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"DeepSeek调用失败: {str(e)}")
    
    def compare_models(self, prompt: str, system_prompt: str = None) -> Dict[str, str]:
        """
        对比多个模型的响应
        
        Args:
            prompt: 测试提示
            system_prompt: 系统提示
            
        Returns:
            各模型响应字典
        """
        results = {}
        
        for model in AIModel:
            if self.available_models.get(model, False):
                try:
                    start = time.time()
                    response = self.generate_response(prompt, system_prompt, model=model)
                    latency = time.time() - start
                    results[model.value] = {
                        'response': response,
                        'latency_ms': round(latency * 1000, 2),
                        'success': not response.startswith(('AI调用失败', '所有AI模型', '未知模型'))
                    }
                except Exception as e:
                    results[model.value] = {
                        'response': str(e),
                        'latency_ms': 0,
                        'success': False
                    }
        
        return results


# 便捷函数
def get_ai_manager() -> MultiModelAI:
    """获取AI管理器单例"""
    if not hasattr(get_ai_manager, '_instance'):
        get_ai_manager._instance = MultiModelAI()
    return get_ai_manager._instance
