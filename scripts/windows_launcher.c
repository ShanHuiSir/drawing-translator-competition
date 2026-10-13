/* A small native Windows GUI launcher. All Python/model files stay in the bundle.
 * No shell command, network connection or installation is performed here.
 */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <wchar.h>
#include <stdio.h>

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command, int show) {
    wchar_t root[32768], python[32768], args[65536];
    DWORD n = GetModuleFileNameW(NULL, root, 32768);
    if (!n || n >= 32768) return 1;
    wchar_t *slash = wcsrchr(root, L'\\');
    if (!slash) return 1;
    *slash = L'\0';
    swprintf(python, 32768, L"%ls\\python\\pythonw.exe", root);
    swprintf(args, 65536, L"\"%ls\" \"%ls\\run_app.py\"", python, root);
    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process = {0};
    startup.cb = sizeof(startup);
    /* Use an explicit executable path. A space in a Chinese username is harmless. */
    if (!CreateProcessW(python, args, NULL, NULL, FALSE, 0, NULL, root, &startup, &process)) {
        MessageBoxW(NULL, L"无法启动图译。请完整解压免安装包，并检查 python 文件夹是否存在。", L"图译", MB_OK | MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD code = 0;
    GetExitCodeProcess(process.hProcess, &code);
    CloseHandle(process.hProcess);
    if (code != 0) {
        MessageBoxW(NULL, L"图译启动或运行失败。详情见同目录 startup.log，也可运行“启动图译.bat”查看提示。", L"图译", MB_OK | MB_ICONERROR);
    }
    return (int)code;
}
