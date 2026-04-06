@echo off
setlocal EnableDelayedExpansion

:: ============================================================
:: PharmaAgent1 Windows 서비스 제거 스크립트 (NSSM 사용)
:: 반드시 관리자 권한으로 실행하십시오.
:: ============================================================

set SERVICE_NAME=PharmaAgent1
set INSTALL_DIR=C:\pharma-agent
set NSSM=%INSTALL_DIR%\tools\nssm\nssm.exe

echo.
echo ============================================================
echo  PharmaAgent1 서비스 제거
echo ============================================================
echo.

:: --- 관리자 권한 확인 ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [오류] 관리자 권한이 필요합니다.
    echo 이 스크립트를 마우스 오른쪽 클릭 후 "관리자로 실행"을 선택하십시오.
    pause
    exit /b 1
)
echo [OK] 관리자 권한 확인

:: --- 서비스 존재 여부 확인 ---
sc query "%SERVICE_NAME%" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] %SERVICE_NAME% 서비스가 등록되어 있지 않습니다.
    pause
    exit /b 0
)

echo [INFO] %SERVICE_NAME% 서비스를 발견했습니다. 제거를 진행합니다.
echo.

:: --- 서비스 중지 ---
echo [INFO] 서비스를 중지합니다...
sc stop "%SERVICE_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] 서비스 중지 요청 완료. 프로세스 종료 대기 중...
    timeout /t 5 /nobreak >nul
) else (
    echo [INFO] 서비스가 이미 중지 상태이거나 응답 없음. 계속 진행합니다.
)

:: --- NSSM으로 서비스 제거 ---
if exist "%NSSM%" (
    echo [INFO] NSSM으로 서비스를 제거합니다...
    "%NSSM%" remove "%SERVICE_NAME%" confirm
    if %errorlevel% equ 0 (
        echo [OK] NSSM 서비스 제거 완료
    ) else (
        echo [경고] NSSM 제거 실패. sc delete로 재시도합니다...
        sc delete "%SERVICE_NAME%"
    )
) else (
    echo [INFO] NSSM을 찾을 수 없습니다. sc delete로 서비스를 제거합니다...
    sc delete "%SERVICE_NAME%"
    if %errorlevel% equ 0 (
        echo [OK] sc delete 서비스 제거 완료
    ) else (
        echo [오류] 서비스 제거에 실패했습니다.
        echo 수동으로 services.msc 또는 sc delete %SERVICE_NAME% 를 실행하십시오.
        pause
        exit /b 1
    )
)

:: --- 제거 확인 ---
sc query "%SERVICE_NAME%" >nul 2>&1
if %errorlevel% neq 0 (
    echo [OK] %SERVICE_NAME% 서비스가 성공적으로 제거되었습니다.
) else (
    echo [경고] 서비스가 아직 등록된 상태입니다. 재부팅 후 완전히 제거될 수 있습니다.
)

echo.
echo ============================================================
echo  제거 완료
echo  로그 파일은 보존됩니다: %INSTALL_DIR%\agent1\logs\
echo  로그를 삭제하려면 해당 폴더를 직접 정리하십시오.
echo ============================================================
echo.
pause
endlocal
