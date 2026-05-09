from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Conversation, Message, AIPersonality,
    WaifuConversation, WaifuMessage,
    SystemSetting, PromptTemplate, User
)


# 自定义 Conversation Admin
@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'session_id', 'title', 'user_link', 'message_count', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['session_id', 'title']
    readonly_fields = ['session_id', 'created_at', 'updated_at']
    ordering = ['-updated_at']

    def user_link(self, obj):
        if obj.user:
            return format_html('<a href="/admin/chat/user/{}/change/">{}</a>', obj.user.id, obj.user.username)
        return '-'

    user_link.short_description = '用户'

    def message_count(self, obj):
        return obj.messages.count()

    message_count.short_description = '消息数'


# 自定义 Message Admin
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation_link', 'role', 'content_preview', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['content']
    readonly_fields = ['created_at']

    def conversation_link(self, obj):
        return format_html('<a href="/admin/chat/conversation/{}/change/">{}</a>', obj.conversation.id,
                           obj.conversation.title)

    conversation_link.short_description = '对话'

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content

    content_preview.short_description = '内容预览'


# 自定义 AIPersonality Admin
@admin.register(AIPersonality)
class AIPersonalityAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'avatar_emoji', 'is_active', 'is_default', 'created_at']
    list_filter = ['is_active', 'is_default', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['is_active', 'is_default']

    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'description', 'avatar_emoji')
        }),
        ('提示词', {
            'fields': ('system_prompt',),
            'classes': ('wide',)
        }),
        ('状态', {
            'fields': ('is_active', 'is_default')
        }),
    )


# 自定义 WaifuConversation Admin
@admin.register(WaifuConversation)
class WaifuConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'session_id', 'title', 'user_link', 'personality', 'message_count', 'created_at']
    list_filter = ['created_at', 'personality']
    search_fields = ['session_id', 'title']
    readonly_fields = ['session_id', 'created_at', 'updated_at']

    def user_link(self, obj):
        if obj.user:
            return format_html('<a href="/admin/chat/user/{}/change/">{}</a>', obj.user.id, obj.user.username)
        return '-'

    user_link.short_description = '用户'

    def message_count(self, obj):
        return obj.waifu_messages.count()

    message_count.short_description = '消息数'


# 自定义 WaifuMessage Admin
@admin.register(WaifuMessage)
class WaifuMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation_link', 'role', 'content_preview', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['content']
    readonly_fields = ['created_at']

    def conversation_link(self, obj):
        return format_html('<a href="/admin/chat/waifuconversation/{}/change/">{}</a>', obj.conversation.id,
                           obj.conversation.title)

    conversation_link.short_description = '对话'

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content

    content_preview.short_description = '内容预览'


# 自定义 SystemSetting Admin
@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'value_preview', 'value_type', 'updated_at']
    list_filter = ['value_type', 'updated_at']
    search_fields = ['key', 'description']

    def value_preview(self, obj):
        return obj.value[:50] + '...' if len(obj.value) > 50 else obj.value

    value_preview.short_description = '值'


# 自定义 PromptTemplate Admin
@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'category', 'content_preview', 'sort_order', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['title', 'content']
    list_editable = ['sort_order']

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content

    content_preview.short_description = '内容预览'


# 自定义 User Admin
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'email', 'first_name', 'avatar_display', 'conversation_count', 'is_active',
                    'date_joined']
    list_filter = ['is_active', 'is_staff', 'date_joined']
    search_fields = ['username', 'email', 'first_name']
    list_editable = ['is_active']

    fieldsets = (
        ('账户信息', {
            'fields': ('username', 'email', 'password')
        }),
        ('个人信息', {
            'fields': ('first_name', 'last_name', 'avatar', 'bio')
        }),
        ('偏好设置', {
            'fields': ('preferred_model',)
        }),
        ('权限', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('时间信息', {
            'fields': ('last_login', 'date_joined')
        }),
    )
    readonly_fields = ['last_login', 'date_joined']

    def avatar_display(self, obj):
        if obj.avatar:
            if obj.avatar.startswith('data:image') or obj.avatar.startswith('http'):
                return format_html(
                    '<img src="{}" style="width: 30px; height: 30px; border-radius: 50%; object-fit: cover;">',
                    obj.avatar)
            return obj.avatar
        return '👤'

    avatar_display.short_description = '头像'

    def conversation_count(self, obj):
        return obj.conversations.count()

    conversation_count.short_description = '对话数'