from django.http import StreamingHttpResponse
from .models import WaifuMessage, AIPersonality, WaifuConversation, SystemSetting, Conversation, Message, PromptTemplate
import uuid
import ollama
import re
import json
import os
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .agent_service import work_agent, get_agent_response_stream
from openai import OpenAI
from datetime import datetime, timedelta
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib.auth import update_session_auth_hash
from django.db.models import Count


DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

@csrf_exempt
def chat_with_local_ai(request):
    # 同时支持 GET（流式）和 POST
    if request.method == 'GET':
        user_prompt = request.GET.get('prompt', '').strip()
        model_name = request.GET.get('model', 'qwen2:7b')
    elif request.method == 'POST':
        user_prompt = request.POST.get('prompt', '').strip()
        model_name = request.POST.get('model', 'qwen2:7b')
    else:
        return JsonResponse({'error': 'Method Not Allowed'}, status=405)

    if not user_prompt:
        return JsonResponse({'error': '请输入内容'}, status=400)

    # 获取会话ID
    session_id = request.COOKIES.get('session_id', 'default_session')

    # 1. 获取/创建会话
    conv, created = Conversation.objects.get_or_create(session_id=session_id)

    # 如果是新对话，用用户的第一条消息当作标题
    if created or conv.title == "新对话":
        conv.title = user_prompt[:20] + "..." if len(user_prompt) > 20 else user_prompt
        conv.save()

    # 2. 保存本条用户消息到数据库
    Message.objects.create(
        conversation=conv,
        role="user",
        content=user_prompt
    )

    # 3. 从数据库读取历史全部上下文
    history = Message.objects.filter(conversation=conv).order_by("created_at")
    context_list = []
    for msg in history:
        context_list.append({
            "role": msg.role,
            "content": msg.content
        })

    # 4. 判断使用本地模型还是 DeepSeek
    if model_name == "deepseek-chat":
        # 使用 DeepSeek API
        def generate():
            full_response = ""
            try:
                client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=context_list,
                    stream=True
                )

                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        clean_content = re.sub(r'[\x00-\x1F\x7F\u200B-\u200F\uFEFF]', '', content)
                        full_response += clean_content
                        yield f"data: {json.dumps({'content': clean_content})}\n\n"

                # AI回复完整后，存入数据库
                Message.objects.create(
                    conversation=conv,
                    role="assistant",
                    content=full_response
                )
                yield f"data: {json.dumps({'done': True})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response.set_cookie('session_id', session_id, max_age=30 * 24 * 60 * 60)
        return response

    else:
        # 使用本地 Ollama
        def generate():
            full_response = ""
            try:
                response = ollama.chat(
                    model=model_name,
                    messages=context_list,
                    stream=True
                )

                for chunk in response:
                    if chunk['message']['content']:
                        content = chunk['message']['content']
                        clean_content = re.sub(r'[\x00-\x1F\x7F\u200B-\u200F\uFEFF]', '', content)
                        full_response += clean_content
                        yield f"data: {json.dumps({'content': clean_content})}\n\n"

                # AI回复完整后，存入数据库
                Message.objects.create(
                    conversation=conv,
                    role="assistant",
                    content=full_response
                )
                yield f"data: {json.dumps({'done': True})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response.set_cookie('session_id', session_id, max_age=30 * 24 * 60 * 60)
        return response

def conversation_list(request):
    convs = Conversation.objects.all().order_by("-updated_at")
    data = [{"session_id": c.session_id, "title": c.title} for c in convs]
    return JsonResponse(data, safe=False)

def rename_conversation(request, session_id): # 重命名
    if request.method == "POST":
        data = json.loads(request.body)
        conv = get_object_or_404(Conversation, session_id=session_id)
        conv.title = data.get("title", conv.title)
        conv.save()
        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "方法不允许"}, status=405)

def delete_single_message(request, session_id, msg_index): # 删除单条对话
    conv = get_object_or_404(Conversation, session_id=session_id)
    messages = list(conv.messages.all().order_by("created_at"))
    if 0 <= msg_index < len(messages):
        messages[msg_index].delete()
    return JsonResponse({"status": "ok"})

@csrf_exempt
def clear_context(request):
    """清空数据库当前会话所有上下文（不删除会话本身）"""
    if request.method == 'POST':
        session_id = request.COOKIES.get('session_id', 'default_session')
        conv = Conversation.objects.filter(session_id=session_id).first()
        if conv:
            Message.objects.filter(conversation=conv).delete()
            # 可选：清空后重置标题为“新对话”
            conv.title = "新对话"
            conv.save()
        return JsonResponse({'status': 'ok'})
    # 处理非POST请求
    return JsonResponse({'error': '仅支持POST请求'}, status=405)

@csrf_exempt
def load_conversation(request, session_id):
    """加载指定会话的所有历史消息，前端切换对话时调用"""
    conv = get_object_or_404(Conversation, session_id=session_id)
    messages = list(conv.messages.values("role", "content", "created_at"))
    return JsonResponse({"messages": messages, "title": conv.title})


@csrf_exempt
def delete_conversation(request, session_id):
    """删除指定会话，同时删除对应的所有消息"""
    if request.method == "POST":
        conv = get_object_or_404(Conversation, session_id=session_id)
        conv.delete()  # 级联删除所有Message
        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "仅支持POST请求"}, status=405)

# 看板娘页面
def waifu_chat(request):
    return render(request, "waifu_chat.html")

# 看板娘对话接口（和主聊天接口隔离）
@csrf_exempt
# views.py 中修改 waifu_chat_api 函数

# views.py 中修改 waifu_chat_api 函数

def waifu_chat_api(request):
    if request.method != "GET":
        return JsonResponse({"error": "请求方式错误"}, status=405)

    prompt = request.GET.get("prompt", "").strip()
    model_name = request.GET.get("model", "qwen2:7b")
    personality_id = request.GET.get("personality_id", "")

    if not prompt:
        return JsonResponse({"error": "内容不能为空"}, status=400)

    # 看板娘专属会话ID前缀
    session_id = request.COOKIES.get("waifu_session_id")
    if not session_id:
        session_id = f"waifu_{uuid.uuid4()}"

    conv, _ = WaifuConversation.objects.get_or_create(session_id=session_id)

    # 获取人设
    personality = None
    if personality_id:
        try:
            personality = AIPersonality.objects.get(id=personality_id)
        except AIPersonality.DoesNotExist:
            pass

    if not personality:
        personality = AIPersonality.objects.filter(is_active=True).first()

    if not personality:
        personality = AIPersonality.objects.filter(is_default=True).first()

    # 更新会话的人设关联
    if personality and conv.personality_id != personality.id:
        conv.personality = personality
        conv.save()

    if not conv.title or conv.title == "新对话":
        conv.title = prompt[:20] if len(prompt) <= 20 else prompt[:20] + "..."
        conv.save()

    # 保存用户消息
    WaifuMessage.objects.create(
        conversation=conv,
        role="user",
        content=prompt
    )

    # 拼接当前会话历史
    msg_qs = WaifuMessage.objects.filter(conversation=conv).order_by("created_at")
    messages = [{"role": m.role, "content": m.content} for m in msg_qs]

    # 使用人设的系统提示词
    if personality:
        system_prompt = personality.system_prompt
    else:
        system_prompt = "你是看板娘Tia，一个活泼可爱、有点小傲娇的二次元少女。说话要软萌，带点语气词，比如~、嘛、呀，偶尔会撒娇、吐槽，像朋友一样陪用户闲聊，不要太严肃，保持轻松愉快的氛围。"

    messages.insert(0, {
        "role": "system",
        "content": system_prompt
    })

    # 判断使用本地模型还是 DeepSeek
    if model_name == "deepseek-chat":
        def stream_gen():
            full_resp = ""
            try:
                client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    stream=True
                )

                for chunk in response:
                    if chunk.choices[0].delta.content:
                        txt = chunk.choices[0].delta.content
                        full_resp += txt
                        yield f"data: {json.dumps({'content': txt})}\n\n"

                WaifuMessage.objects.create(
                    conversation=conv,
                    role="assistant",
                    content=full_resp
                )
                yield f"data: {json.dumps({'done': True})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
    else:
        # 使用本地 Ollama
        def stream_gen():
            full_resp = ""
            res = ollama.chat(
                model=model_name,
                messages=messages,
                stream=True
            )
            for chunk in res:
                txt = chunk["message"]["content"]
                if txt:
                    full_resp += txt
                    yield f"data: {json.dumps({'content': txt})}\n\n"

            WaifuMessage.objects.create(
                conversation=conv,
                role="assistant",
                content=full_resp
            )
            yield f"data: {json.dumps({'done': True})}\n\n"

    resp = StreamingHttpResponse(stream_gen(), content_type="text/event-stream")
    resp.set_cookie("waifu_session_id", session_id, max_age=30 * 24 * 60 * 60)
    return resp


# 新增：获取人设列表API
def get_personalities_for_chat(request):
    """获取用于对话的人设列表"""
    personalities = AIPersonality.objects.all()
    data = [{
        'id': p.id,
        'name': p.name,
        'avatar_emoji': p.avatar_emoji,
        'is_active': p.is_active
    } for p in personalities]
    return JsonResponse({'success': True, 'data': data})


# 新增：切换会话人设
@csrf_exempt
def switch_session_personality(request, session_id):
    """切换会话的人设"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            personality_id = data.get('personality_id')

            conv = get_object_or_404(WaifuConversation, session_id=session_id)
            personality = get_object_or_404(AIPersonality, id=personality_id)

            conv.personality = personality
            conv.save()

            return JsonResponse({'success': True, 'message': f'已切换人设：{personality.name}'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': '方法不允许'}, status=405)

# 【仅用于 waifu_chat.html 左侧对话列表】
def waifu_list(request):
    # 只读 WaifuConversation，绝不碰 Conversation
    convs = WaifuConversation.objects.all().order_by("-updated_at")
    data = [{"session_id": c.session_id, "title": c.title} for c in convs]
    return JsonResponse(data, safe=False)

# 【加载看板娘某条对话历史】
def waifu_load(request, session_id):
    conv = get_object_or_404(WaifuConversation, session_id=session_id)
    messages = list(conv.waifu_messages.values("role", "content"))
    return JsonResponse({"messages": messages})

# 【删除看板娘对话】
@csrf_exempt
def waifu_delete(request, session_id):
    if request.method == "POST":
        conv = get_object_or_404(WaifuConversation, session_id=session_id)
        conv.delete()  # 只删看板娘数据
        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "方法不允许"}, status=405)

# 【清空当前看板娘对话】
@csrf_exempt
def waifu_clear(request):
    if request.method == "POST":
        session_id = request.COOKIES.get("waifu_session_id")
        if session_id:
            conv = WaifuConversation.objects.filter(session_id=session_id).first()
            if conv:
                WaifuMessage.objects.filter(conversation=conv).delete()
        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "方法不允许"}, status=405)

# 看板娘界面 - 删除单条消息
@csrf_exempt
def waifu_delete_single_message(request, session_id, msg_index):
    conv = get_object_or_404(WaifuConversation, session_id=session_id)
    # 用你模型的 related_name：waifu_messages
    messages = list(conv.waifu_messages.all().order_by("created_at"))
    if 0 <= msg_index < len(messages):
        messages[msg_index].delete()
    return JsonResponse({"status": "ok"})


# ========== 人设管理界面 ==========
def personality_manager(request):
    """人设管理页面"""
    personalities = AIPersonality.objects.all()
    active_personality = AIPersonality.objects.filter(is_active=True).first()
    return render(request, 'personality_manager.html', {
        'personalities': personalities,
        'active_personality': active_personality
    })


# ========== 人设 CRUD API ==========
@csrf_exempt
def personality_list(request):
    """获取所有人设列表"""
    if request.method == 'GET':
        personalities = AIPersonality.objects.all()
        data = [{
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'system_prompt': p.system_prompt,
            'avatar_emoji': p.avatar_emoji,
            'is_active': p.is_active,
            'is_default': p.is_default,
            'created_at': p.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for p in personalities]
        return JsonResponse({'success': True, 'data': data})

    return JsonResponse({'success': False, 'error': '方法不允许'}, status=405)


@csrf_exempt
def personality_create(request):
    """创建新的人设"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            # 如果设置这个为新默认，移除其他默认
            if data.get('is_default', False):
                AIPersonality.objects.filter(is_default=True).update(is_default=False)

            # 如果设置这个为激活，移除其他激活
            if data.get('is_active', False):
                AIPersonality.objects.filter(is_active=True).update(is_active=False)

            personality = AIPersonality.objects.create(
                name=data.get('name', '新的人设'),
                description=data.get('description', '暂无描述'),
                system_prompt=data.get('system_prompt', '你是一个友好的AI助手。'),
                avatar_emoji=data.get('avatar_emoji', '💬'),
                is_active=data.get('is_active', False),
                is_default=data.get('is_default', False)
            )

            return JsonResponse({
                'success': True,
                'message': '人设创建成功',
                'data': {
                    'id': personality.id,
                    'name': personality.name,
                    'description': personality.description,
                    'system_prompt': personality.system_prompt,
                    'avatar_emoji': personality.avatar_emoji,
                    'is_active': personality.is_active,
                    'is_default': personality.is_default
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': '方法不允许'}, status=405)


@csrf_exempt
def personality_update(request, personality_id):
    """更新人设"""
    if request.method == 'POST':
        try:
            personality = get_object_or_404(AIPersonality, id=personality_id)
            data = json.loads(request.body)

            # 处理默认标志
            if data.get('is_default', False):
                AIPersonality.objects.filter(is_default=True).exclude(id=personality_id).update(is_default=False)
                personality.is_default = True

            # 处理激活标志
            if data.get('is_active', False):
                AIPersonality.objects.filter(is_active=True).exclude(id=personality_id).update(is_active=False)
                personality.is_active = True

            # 更新字段
            personality.name = data.get('name', personality.name)
            personality.description = data.get('description', personality.description)
            personality.system_prompt = data.get('system_prompt', personality.system_prompt)
            personality.avatar_emoji = data.get('avatar_emoji', personality.avatar_emoji)

            # 如果没有设置激活且是唯一激活的，保持激活
            if not data.get('is_active', False) and personality.is_active:
                # 检查是否还有其他激活的
                if not AIPersonality.objects.filter(is_active=True).exclude(id=personality_id).exists():
                    personality.is_active = True
                else:
                    personality.is_active = False

            personality.save()

            return JsonResponse({
                'success': True,
                'message': '人设更新成功',
                'data': {
                    'id': personality.id,
                    'name': personality.name,
                    'description': personality.description,
                    'system_prompt': personality.system_prompt,
                    'avatar_emoji': personality.avatar_emoji,
                    'is_active': personality.is_active,
                    'is_default': personality.is_default
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': '方法不允许'}, status=405)


@csrf_exempt
def personality_delete(request, personality_id):
    """删除人设"""
    if request.method == 'POST':
        try:
            personality = get_object_or_404(AIPersonality, id=personality_id)

            # 不允许删除默认人设
            if personality.is_default:
                return JsonResponse({'success': False, 'error': '不能删除默认人设'}, status=400)

            personality.delete()
            return JsonResponse({'success': True, 'message': '人设删除成功'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': '方法不允许'}, status=405)


@csrf_exempt
def personality_set_active(request, personality_id):
    """设置激活人设"""
    if request.method == 'POST':
        try:
            # 将所有其他人设设为非激活
            AIPersonality.objects.filter(is_active=True).update(is_active=False)

            # 设置当前人设为激活
            personality = get_object_or_404(AIPersonality, id=personality_id)
            personality.is_active = True
            personality.save()

            return JsonResponse({
                'success': True,
                'message': f'已切换到人设：{personality.name}'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': '方法不允许'}, status=405)


@csrf_exempt
def personality_preview(request):
    """预览人设效果（测试对话）"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            prompt = data.get('prompt', '').strip()
            personality_id = data.get('personality_id')

            if not prompt:
                return JsonResponse({'success': False, 'error': '请输入测试内容'}, status=400)

            # 获取人设
            if personality_id:
                personality = get_object_or_404(AIPersonality, id=personality_id)
                system_prompt = personality.system_prompt
                personality_name = personality.name
            else:
                # 使用当前激活的人设
                personality = AIPersonality.objects.filter(is_active=True).first()
                if not personality:
                    return JsonResponse({'success': False, 'error': '请先创建并激活一个人设'}, status=400)
                system_prompt = personality.system_prompt
                personality_name = personality.name

            # 调用AI进行预览（非流式）
            import ollama
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]

            response = ollama.chat(
                model="qwen2:7b",
                messages=messages,
                stream=False
            )

            return JsonResponse({
                'success': True,
                'response': response['message']['content'],
                'personality_name': personality_name
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': '方法不允许'}, status=405)

@csrf_exempt
def chat_with_agent(request):
    """
    带 Agent 能力的对话接口
    支持 GET（流式）请求
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Method Not Allowed'}, status=405)

    user_prompt = request.GET.get('prompt', '').strip()
    model_name = request.GET.get('model', 'qwen2:7b')

    if not user_prompt:
        return JsonResponse({'error': '请输入内容'}, status=400)

    # 更新Agent的模型（如果需要）
    work_agent.model = model_name

    # 获取会话ID
    session_id = request.COOKIES.get('session_id', 'default_session')

    # 获取/创建会话
    conv, created = Conversation.objects.get_or_create(session_id=session_id)

    # 保存用户消息
    Message.objects.create(
        conversation=conv,
        role="user",
        content=user_prompt
    )

    # 保存用户消息人设消息
    def generate_with_save():
        full_response = ""

        # 调用Agent获取流式响应
        for chunk in get_agent_response_stream(user_prompt):
            data = json.loads(chunk.replace("data: ", "").strip())

            if data.get('content'):
                full_response += data['content']
                yield f"data: {json.dumps({'content': data['content']})}\n\n"

            if data.get('done'):
                # 保存AI回复
                Message.objects.create(
                    conversation=conv,
                    role="assistant",
                    content=full_response
                )
                yield f"data: {json.dumps({'done': True})}\n\n"
                break

    response = StreamingHttpResponse(generate_with_save(), content_type='text/event-stream')
    response.set_cookie('session_id', session_id, max_age=30 * 24 * 60 * 60)
    return response

@csrf_exempt
def settings_load(request):
    """加载所有设置"""
    if request.method == 'GET':
        settings = SystemSetting.objects.all()
        data = {}
        for s in settings:
            if s.value_type == "bool":
                data[s.key] = s.value.lower() == "true"
            elif s.value_type == "int":
                data[s.key] = int(s.value)
            elif s.value_type == "json":
                import json
                data[s.key] = json.loads(s.value)
            else:
                data[s.key] = s.value
        return JsonResponse({'success': True, 'data': data})

    return JsonResponse({'success': False, 'error': '方法不允许'})


@csrf_exempt
def settings_save(request):
    """保存单个设置"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            key = data.get('key')
            value = data.get('value')
            value_type = data.get('value_type', 'str')
            description = data.get('description', '')

            SystemSetting.set(key, value, value_type, description)

            return JsonResponse({'success': True, 'message': '保存成功'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': '方法不允许'})


@csrf_exempt
def settings_batch_save(request):
    """批量保存设置"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            settings = data.get('settings', [])

            for setting in settings:
                SystemSetting.set(
                    setting.get('key'),
                    setting.get('value'),
                    setting.get('value_type', 'str'),
                    setting.get('description', '')
                )

            return JsonResponse({'success': True, 'message': '保存成功'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': '方法不允许'})

# views.py 中添加

def about_page(request):
    """关于页面"""
    return render(request, 'about.html')

def templates_page(request):
    """帮助教程页面"""
    return render(request, 'templates.html')

@csrf_exempt
def stats_api(request):
    """获取统计数据"""
    if request.method == 'GET':
        total_chats = Conversation.objects.count()
        total_messages = Message.objects.count()

        # 平均消息长度
        from django.db.models import Avg, functions
        avg_result = Message.objects.aggregate(avg_len=Avg(functions.Length('content')))
        avg_length = int(avg_result.get('avg_len', 0) or 0)

        # 最近7天数据
        today = datetime.now().date()
        week_data = []
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            count = Message.objects.filter(
                created_at__date=date
            ).count()
            week_data.append({
                'date': date.strftime('%m-%d'),
                'count': count
            })

        # 模型使用分布（简化）
        model_stats = {
            'qwen2:7b': Message.objects.filter(content__isnull=False).count() // 2 if total_messages > 0 else 0,
            'deepseek-chat': total_messages // 3 if total_messages > 0 else 0
        }

        return JsonResponse({
            'success': True,
            'data': {
                'total_chats': total_chats,
                'total_messages': total_messages,
                'avg_message_length': avg_length,
                'week_data': week_data,
                'model_stats': model_stats
            }
        })

    return JsonResponse({'success': False, 'error': 'Method Not Allowed'})


# 提示词 CRUD
@csrf_exempt
def prompts_api(request, prompt_id=None):
    if request.method == 'GET':
        if prompt_id:
            try:
                prompt = PromptTemplate.objects.get(id=prompt_id)
                return JsonResponse({
                    'success': True,
                    'data': {
                        'id': prompt.id,
                        'title': prompt.title,
                        'content': prompt.content,
                        'category': prompt.category
                    }
                })
            except PromptTemplate.DoesNotExist:
                return JsonResponse({'success': False, 'error': '提示词不存在'})
        else:
            prompts = PromptTemplate.objects.all()
            data = [{
                'id': p.id,
                'title': p.title,
                'content': p.content,
                'category': p.category
            } for p in prompts]
            return JsonResponse({'success': True, 'data': data})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            prompt = PromptTemplate.objects.create(
                title=data.get('title'),
                content=data.get('content'),
                category=data.get('category', 'general')
            )
            return JsonResponse({'success': True, 'message': '创建成功', 'data': {'id': prompt.id}})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    elif request.method == 'PUT' and prompt_id:
        try:
            prompt = get_object_or_404(PromptTemplate, id=prompt_id)
            data = json.loads(request.body)
            prompt.title = data.get('title', prompt.title)
            prompt.content = data.get('content', prompt.content)
            prompt.category = data.get('category', prompt.category)
            prompt.save()
            return JsonResponse({'success': True, 'message': '更新成功'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    elif request.method == 'DELETE' and prompt_id:
        try:
            prompt = get_object_or_404(PromptTemplate, id=prompt_id)
            prompt.delete()
            return JsonResponse({'success': True, 'message': '删除成功'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Method Not Allowed'})


def login_view(request):
    """登录页面"""
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('/')
    else:
        form = AuthenticationForm()

    return render(request, 'login.html', {'form': form})


def register_view(request):
    """注册页面"""
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('/')
    else:
        form = UserCreationForm()

    return render(request, 'register.html', {'form': form})


def logout_view(request):
    """登出"""
    logout(request)
    return redirect('/login/')


# 修改现有视图，添加登录保护
from django.contrib.auth.decorators import login_required


@login_required
def chat_page(request):
    """渲染对话页面"""
    # 只显示当前用户的对话
    conversations = Conversation.objects.filter(user=request.user).order_by("-updated_at")
    return render(request, 'chat.html', {'conversations': conversations})


@login_required
def waifu_chat(request):
    return render(request, "waifu_chat.html")


@login_required
def personality_manager(request):
    """人设管理页面"""
    personalities = AIPersonality.objects.all()
    active_personality = AIPersonality.objects.filter(is_active=True).first()
    return render(request, 'personality_manager.html', {
        'personalities': personalities,
        'active_personality': active_personality
    })


@login_required
def settings_page(request):
    """系统设置页面"""
    return render(request, 'settings.html')


@login_required
def profile_page(request):
    """个人中心页面"""
    return render(request, 'profile.html')


@login_required
def user_profile_api(request):
    """获取/更新用户资料"""
    if request.method == 'GET':
        # 获取用户统计数据
        conversations = Conversation.objects.filter(user=request.user).count()
        messages = Message.objects.filter(conversation__user=request.user).count()

        # 计算活跃天数（简单实现）
        from datetime import datetime, timedelta
        first_conversation = Conversation.objects.filter(user=request.user).order_by('created_at').first()
        if first_conversation:
            days = (datetime.now().date() - first_conversation.created_at.date()).days + 1
        else:
            days = 1

        data = {
            'username': request.user.username,
            'first_name': request.user.first_name or '',
            'avatar': request.user.avatar,
            'bio': request.user.bio or '',
            'preferred_model': request.user.preferred_model,
            'date_joined': request.user.date_joined.isoformat(),
            'stats': {
                'conversations': conversations,
                'messages': messages,
                'active_days': max(1, days)
            }
        }
        return JsonResponse({'success': True, 'data': data})

    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            if 'avatar' in data:
                request.user.avatar = data['avatar']
            if 'first_name' in data:
                request.user.first_name = data['first_name']
            if 'bio' in data:
                request.user.bio = data['bio']
            request.user.save()
            return JsonResponse({'success': True, 'message': '更新成功'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': '方法不允许'})


@login_required
def user_change_password_api(request):
    """修改密码"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            old_password = data.get('old_password')
            new_password = data.get('new_password')

            if not request.user.check_password(old_password):
                return JsonResponse({'success': False, 'error': '当前密码错误'})

            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)

            return JsonResponse({'success': True, 'message': '密码修改成功'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': '方法不允许'})


@login_required
def user_preferences_api(request):
    """更新用户偏好"""
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            if 'preferred_model' in data:
                request.user.preferred_model = data['preferred_model']
            request.user.save()
            return JsonResponse({'success': True, 'message': '保存成功'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': '方法不允许'})