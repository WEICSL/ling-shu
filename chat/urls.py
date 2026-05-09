from django.urls import path
from .import views
urlpatterns = [
    # 用户认证
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    # 对话页面路由
    path('', views.chat_page, name='chat_page'),
    # 对话接口路由
    path('api/chat/', views.chat_with_local_ai, name='chat_with_local_ai'),
    # 清空上下文
    path('api/chat/clear/', views.clear_context, name='clear_context'),
    # 加载指定对话的历史记录
    path("conversations/<str:session_id>/load/", views.load_conversation, name="load_conversation"),
    # 删除指定会话
    path("conversations/<str:session_id>/delete/", views.delete_conversation, name="delete_conversation"),
    # 历史对话栏
    path("conversations/list/", views.conversation_list, name="conv_list"),
    # 重命名
    path("conversations/<str:session_id>/rename/", views.rename_conversation, name="rename_conv"),
    # 删除单句对话
    path("conversations/<str:session_id>/message/<int:msg_index>/delete/", views.delete_single_message, name="del_msg"),
    # 看板娘对话路由
    path('waifu/', views.waifu_chat, name='waifu_chat'),
    # 看板娘对话接口路由
    path('waifu/api/', views.waifu_chat_api, name='waifu_chat_api'),
    # 看板娘对话历史栏
    path('waifu/list/', views.waifu_list),
    # 看板娘加载历史对话
    path('waifu/load/<str:session_id>/', views.waifu_load),
    # 看板娘删除指定对话
    path('waifu/delete/<str:session_id>/', views.waifu_delete),
     # 看板娘清空上下文
    path('waifu/clear/', views.waifu_clear),
    # 看板娘单条消息删除
    path('waifu/message/<str:session_id>/<int:msg_index>/delete/', views.waifu_delete_single_message),
    # 人设管理
    path('personality/', views.personality_manager, name='personality_manager'),
    path('personality/list/', views.personality_list, name='personality_list'),
    path('personality/create/', views.personality_create, name='personality_create'),
    path('personality/update/<str:personality_id>/', views.personality_update, name='personality_update'),
    path('personality/delete/<str:personality_id>/', views.personality_delete, name='personality_delete'),
    path('personality/set-active/<str:personality_id>/', views.personality_set_active, name='personality_set_active'),
    path('personality/preview/', views.personality_preview, name='personality_preview'),
    # 看板娘人设相关
    path('waifu/personalities/', views.get_personalities_for_chat, name='get_personalities_for_chat'),
    path('waifu/switch-personality/<str:session_id>/', views.switch_session_personality, name='switch_session_personality'),
    # Agent 对话接口（带工具调用）
    path('api/agent/', views.chat_with_agent, name='chat_with_agent'),
    # 系统设置
    path('settings/', views.settings_page, name='settings'),
    path('api/settings/load/', views.settings_load, name='settings_load'),
    path('api/settings/save/', views.settings_save, name='settings_save'),
    path('api/settings/batch/', views.settings_batch_save, name='settings_batch_save'),
    # 关于界面
    path('about/', views.about_page, name='about'),
    # 帮助界面
    path('templates/', views.templates_page, name='templates'),
    # 提示词和统计面版
    path('api/stats/', views.stats_api, name='stats_api'),
    path('api/prompts/', views.prompts_api, name='prompts_api'),
    path('api/prompts/<int:prompt_id>/', views.prompts_api, name='prompts_api_detail'),
    # 个人中心
    path('profile/', views.profile_page, name='profile'),
    path('api/user/profile/', views.user_profile_api, name='user_profile_api'),
    path('api/user/change-password/', views.user_change_password_api, name='user_change_password_api'),
    path('api/user/preferences/', views.user_preferences_api, name='user_preferences_api'),
]