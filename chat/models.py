from django.db import models
import uuid
from django.contrib.auth.models import AbstractUser


# ========== 1. 先定义 User ==========
class User(AbstractUser):
    """自定义用户模型"""
    avatar = models.TextField(default="👤", verbose_name="头像")
    bio = models.TextField(blank=True, max_length=200, verbose_name="个人简介")
    preferred_model = models.CharField(max_length=50, default="deepseek-chat", verbose_name="偏好模型")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user"
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def __str__(self):
        return self.username


# ========== 2. Conversation 和 Message ==========
class Conversation(models.Model):
    # 修改为字符串引用 'User'
    user = models.ForeignKey(
        'User',  # 改成字符串
        on_delete=models.CASCADE,
        related_name="conversations",
        null=True,
        blank=True
    )
    session_id = models.CharField(max_length=100, unique=True, verbose_name="会话ID")
    title = models.CharField(max_length=100, default="新对话", verbose_name="对话标题")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "对话会话"
        verbose_name_plural = "对话会话"

    def __str__(self):
        return f"会话 {self.session_id}"


class Message(models.Model):
    """单条消息记录"""
    ROLE_CHOICES = (
        ('user', '用户'),
        ('assistant', 'AI助手'),
    )
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages', verbose_name="所属会话")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name="角色")
    content = models.TextField(verbose_name="消息内容")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="发送时间")

    class Meta:
        verbose_name = "消息记录"
        verbose_name_plural = "消息记录"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role}: {self.content[:30]}"


# ========== 3. AIPersonality ==========
class AIPersonality(models.Model):
    """AI人设模型"""
    id = models.CharField(max_length=50, primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name="人设名称")
    description = models.TextField(verbose_name="人设描述")
    system_prompt = models.TextField(verbose_name="系统提示词")
    avatar_emoji = models.CharField(max_length=10, default="💬", verbose_name="头像图标")
    is_active = models.BooleanField(default=False, verbose_name="是否启用")
    is_default = models.BooleanField(default=False, verbose_name="是否默认")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_personality"
        verbose_name = "AI人设"
        verbose_name_plural = "AI人设"
        ordering = ["-is_default", "-is_active", "-created_at"]

    def __str__(self):
        return self.name


# ========== 4. WaifuConversation 和 WaifuMessage ==========
class WaifuConversation(models.Model):
    # 修改为字符串引用 'User'
    user = models.ForeignKey(
        'User',  # 改成字符串
        on_delete=models.CASCADE,
        related_name="waifu_conversations",
        null=True,
        blank=True
    )
    session_id = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=200, default="新对话")
    personality = models.ForeignKey(
        AIPersonality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "看板娘对话"
        verbose_name_plural = "看板娘对话"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.title} ({self.session_id[:8]})"


class WaifuMessage(models.Model):
    conversation = models.ForeignKey(
        WaifuConversation,
        on_delete=models.CASCADE,
        related_name="waifu_messages"
    )
    role = models.CharField(max_length=16)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "看板娘消息"
        verbose_name_plural = "看板娘消息"
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.role}]: {self.content[:30]}"


# ========== 5. SystemSetting ==========
class SystemSetting(models.Model):
    """系统设置"""
    key = models.CharField(max_length=100, unique=True, verbose_name="设置键")
    value = models.TextField(blank=True, verbose_name="设置值")
    value_type = models.CharField(max_length=20, default="str", verbose_name="值类型")
    description = models.CharField(max_length=200, blank=True, verbose_name="描述")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "system_setting"
        verbose_name = "系统设置"
        verbose_name_plural = "系统设置"

    def __str__(self):
        return f"{self.key} = {self.value[:50]}"

    @classmethod
    def get(cls, key, default=None):
        try:
            setting = cls.objects.get(key=key)
            if setting.value_type == "bool":
                return setting.value.lower() == "true"
            elif setting.value_type == "int":
                return int(setting.value)
            elif setting.value_type == "json":
                import json
                return json.loads(setting.value)
            return setting.value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value, value_type="str", description=""):
        if value_type == "json":
            import json
            value = json.dumps(value, ensure_ascii=False)
        elif value_type == "bool":
            value = str(value).lower()
        elif value_type == "int":
            value = str(value)

        obj, created = cls.objects.update_or_create(
            key=key,
            defaults={
                "value": str(value),
                "value_type": value_type,
                "description": description
            }
        )
        return obj


# ========== 6. PromptTemplate ==========
class PromptTemplate(models.Model):
    """提示词模板"""
    title = models.CharField(max_length=200, verbose_name="标题")
    content = models.TextField(verbose_name="内容")
    category = models.CharField(max_length=50, default="general", verbose_name="分类")
    sort_order = models.IntegerField(default=0, verbose_name="排序")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prompt_template"
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return self.title