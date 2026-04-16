#SingleInstance Force
; Elevate process priority to ensure CPU time during session switches
ProcessSetPriority "High"

; Force DPI awareness to fix multi-monitor coordinate offset
DllCall("SetProcessDPIAware")

password := "518727"
global screenGuis := []
global isCreating := false  ; Reentrance guard to prevent concurrent GUI creation
global editCtrl := "", txtObj := "", uiGuiHwnd := 0

; Start
CreateLockScreens()

; Periodic focus enforcement timer (every 500ms)
SetTimer(EnforceFocus, 500)

; --- Core function: dynamically capture full virtual space ---

CreateLockScreens() {
    global screenGuis, editCtrl, txtObj, isCreating, uiGuiHwnd

    ; Reentrance guard: prevent concurrent calls from multiple display change events
    if (isCreating)
        return
    isCreating := true

    try {
        ; Destroy all old GUI handles to ensure no residual windows
        for guiObj in screenGuis {
            try guiObj.Destroy()
        }
        screenGuis := []
        uiGuiHwnd := 0

        ; Small delay to let display driver stabilize (critical for GWS virtual screens)
        Sleep(100)

        ; Get primary monitor info (for placing the input box)
        primaryNum := MonitorGetPrimary()
        MonitorGet(primaryNum, &pL, &pT, &pR, &pB)
        pW := pR - pL
        pH := pB - pT

        ; Create a separate background GUI for each monitor to avoid
        ; single giant virtual-screen window rendering issues with GWS/DWM
        monCount := MonitorGetCount()
        Loop monCount {
            MonitorGet(A_Index, &mL, &mT, &mR, &mB)
            mW := mR - mL
            mH := mB - mT

            bgGui := Gui("+AlwaysOnTop -Caption +ToolWindow")
            bgGui.BackColor := "000000"
            ; Use WS_EX_NOACTIVATE (0x08000000) so background won't steal focus
            bgGui.Opt("+E0x08000000")
            bgGui.Show("x" mL " y" mT " w" mW " h" mH " NoActivate")
            screenGuis.Push(bgGui)
        }

        ; Create UI interaction layer on the primary screen
        uiGui := Gui("+AlwaysOnTop -Caption +ToolWindow")
        uiGui.BackColor := "000000"

        ; Center calculation
        editW := 300, editH := 50, textH := 50, gap := 30
        totalHeight := textH + gap + editH
        startY := (pH - totalHeight) / 2

        uiGui.SetFont("s20 cWhite", "Microsoft YaHei")
        txtObj := uiGui.Add("Text", "x0 y" startY " w" pW " h" textH " Center", "系统已锁定，请输入密码解锁")

        editX := (pW - editW) / 2
        editY := startY + textH + gap
        uiGui.SetFont("s18 cBlack")
        editCtrl := uiGui.Add("Edit", "x" editX " y" editY " w" editW " h" editH " Password Center")

        btn := uiGui.Add("Button", "Default w0 h0", "Verify")
        btn.OnEvent("Click", VerifyPassword)

        uiGui.Show("x" pL " y" pT " w" pW " h" pH)
        uiGuiHwnd := uiGui.Hwnd
        screenGuis.Push(uiGui)

        ; Force DWM to flush and repaint all screens after GUI creation
        DllCall("user32.dll\InvalidateRect", "Ptr", 0, "Ptr", 0, "Int", 1)
        DllCall("user32.dll\UpdateWindow", "Ptr", 0)

        ; Delayed focus to ensure window is fully rendered and activated
        Sleep(50)
        try {
            WinActivate(uiGuiHwnd)
            editCtrl.Focus()
        }
    }

    isCreating := false
}

; --- Periodic focus enforcement ---

EnforceFocus() {
    global editCtrl, uiGuiHwnd
    if (!uiGuiHwnd || !IsObject(editCtrl))
        return
    try {
        ; Only re-focus if our UI window is not the active window
        if (WinActive("ahk_id " uiGuiHwnd) == 0) {
            WinActivate(uiGuiHwnd)
        }
        ; Always ensure the edit control has focus
        ControlFocus(editCtrl, "ahk_id " uiGuiHwnd)
    }
}

; --- Deep defense logic for GWS black screen ---

VerifyPassword(*) {
    global editCtrl, password, screenGuis, uiGuiHwnd
    if (editCtrl.Value == password) {
        ; Stop focus enforcement timer
        SetTimer(EnforceFocus, 0)

        ; 1. Remove all topmost attributes
        for guiObj in screenGuis {
            try {
                guiObj.Opt("-AlwaysOnTop")
                guiObj.Hide()
            }
        }

        ; 2. Force system desktop repaint (fix GWS exit black screen residue)
        DllCall("user32.dll\InvalidateRect", "Ptr", 0, "Ptr", 0, "Int", 1)
        DllCall("user32.dll\UpdateWindow", "Ptr", 0)

        ; 3. Additional: send WM_PAINT to desktop window to force refresh
        hDesktop := DllCall("user32.dll\GetDesktopWindow", "Ptr")
        DllCall("user32.dll\InvalidateRect", "Ptr", hDesktop, "Ptr", 0, "Int", 1)
        DllCall("user32.dll\UpdateWindow", "Ptr", hDesktop)

        Sleep(200)
        ExitApp
    } else {
        editCtrl.Value := ""
        editCtrl.Focus()
    }
}

; Throttled display change handler to avoid rapid re-creation
OnDisplayChange(*) {
    static lastCall := 0
    now := A_TickCount
    ; Debounce: ignore if called within 1500ms of last call
    if (now - lastCall < 1500)
        return
    lastCall := now
    SetTimer(CreateLockScreens, -1000)
}

; Listen for display changes (triggered when GWS exits)
OnMessage(0x007E, OnDisplayChange)

; Listen for session changes
OnMessage(0x02B1, OnDisplayChange)

; --- Auxiliary patches ---

; Block keys
!f4::return
LWin::return
RWin::return
; Also block Ctrl+Esc (Start menu alternative)
^Esc::return
; Block Alt+Tab
!Tab::return
; Block Ctrl+Alt+Delete cannot be blocked by AHK, but block Ctrl+Shift+Esc (Task Manager)
^+Esc::return

; Emergency rescue: if still black screen, press Ctrl + Alt + R to force display driver reset
^!r:: {
    global isCreating
    isCreating := false  ; Reset guard in case it's stuck
    CreateLockScreens()
    DllCall("user32.dll\InvalidateRect", "Ptr", 0, "Ptr", 0, "Int", 1)
}

~LButton:: {
    global editCtrl, uiGuiHwnd
    if IsObject(editCtrl) && uiGuiHwnd {
        try {
            WinActivate(uiGuiHwnd)
            editCtrl.Focus()
        }
    }
}