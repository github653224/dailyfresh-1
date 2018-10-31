import re

from django.core.mail import send_mail
from django.http import HttpResponse
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired

from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from django.conf import settings


from apps.users.models import *
from celery_tasks.tasks import send_register_active_email


class RegisterView(View):
    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        cpwd = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '信息不能为空'})
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})
        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意“天天生鲜用户使用协议”'})
        if password != cpwd:
            return render(request, 'register.html', {'errmsg': '两次输入的密码不一致'})

        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None
        if user:
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        user = User.objects.create_user(username=username, password=password, email=email)
        user.is_active = 0
        user.save()

        # 加密用户身份信息，生成激活token
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info)
        token = token.decode('utf8')

        # 发邮件
        send_register_active_email.delay(email, username, token)

        return redirect(reverse('goods:index'))


class ActiveView(View):
    '''用户激活'''
    def get(self, request, token):
        # 解密，获取要激活的用户信息
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            # 获取待激活待激活用户的id
            user_id = info['confirm']
            # 根据id获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            return HttpResponse('激活连接已过期')


class LoginView(View):
    def get(self, request):
        # 判断是否记住了用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''

        return render(request, 'login.html', {'username': username, 'checked': checked})

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': '信息缺失，不合法'})
        user = authenticate(username=username, password=password)
        if user:
            if user.is_active:
                login(request, user)
                # 获取登陆后所要跳转的地址
                next_url = request.GET.get('next', reverse('goods:index'))  # 如果是正常登录，网址后没有next，默认跳转首页
                response = redirect(next_url)
                # 判断用户是否勾选记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    # 记住用户名
                    response.set_cookie('username', user.username, max_age=7*24*3600)
                else:
                    response.delete_cookie('username')
                return response
            else:
                return render(request, 'login.html', {'errmsg': '账户未激活，请到注册邮箱激活'})
        else:
            return render(request, 'login.html', {'errmsg': '账号或密码错误'})


class UserInfoView(View):
    '''用户中心信息'''
    def get(self, request):
        return render(request, 'user_center_info.html', {'page': 'user'})


class UserOrderView(View):
    '''用户中心订单'''
    def get(self, request):
        return render(request, 'user_center_order.html', {'page': 'order'})


class AddressView(View):
    '''用户中心地址'''
    def get(self, request):
        return render(request, 'user_center_site.html', {'page': 'address'})