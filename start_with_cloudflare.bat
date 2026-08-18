@echo off
chcp 65001 > nul
title نظام متابعة وحصر البريد الإلكتروني - Cloudflare Zero Trust
color 0A

echo =======================================================
echo    الهيئة العامة للرعاية الصحية - فرع الأقصر
echo    حساب Cloudflare: magy.a.matta85@gmail.com
echo    اسم النفق: eha-luxor-mail
echo =======================================================
echo.
echo [1/2] جاري تشغيل خادم البرنامج المحلي...
start /b python run.py

timeout /t 3 /nobreak > nul

echo [2/2] جاري الاتصال بنفق Cloudflare الموثق بحسابك...
echo.

.\cloudflared.exe tunnel run --token eyJhIjoiYzVmZmZjNjEyNmM1OTQ1MjNkMzFiMWJlMTU5MTllYWYiLCJ0IjoiYWEyZTUzOWItZmZlNi00Mjg0LTllYmUtOGUyNDA2YTQ3ZTIyIiwicyI6Ill6Z3haamcyTnpjdE1EWTBaQzAwWlRFMUxUa3dZall0WXpZNU5XSmhNbVpoT1dVeiJ9

pause
