#SingleInstance Force
password := "518727"

; 1. 构建一体化锁屏界面
myGui := Gui("+AlwaysOnTop -Caption +ToolWindow")
myGui.BackColor := "000000"

; 添加文字提示
myGui.SetFont("s14 cWhite", "Microsoft YaHei")
myGui.Add("Text", "x0 y" (A_ScreenHeight/2 - 60) " w" A_ScreenWidth/2 " Center", "系统已锁定，请输入密码解锁")

; 添加输入框（隐藏输入内容）
editCtrl := myGui.Add("Edit", "x" (A_ScreenWidth/2 - 100) " y" (A_ScreenHeight/2) " w200 h30 Password")

; 添加一个隐藏的默认按钮，按回车触发验证
btn := myGui.Add("Button", "Default w0 h0", "Verify")
btn.OnEvent("Click", VerifyPassword)

; 2. 显示全屏
myGui.Show("x0 y0 w" A_ScreenWidth " h" A_ScreenHeight)

; 自动聚焦到输入框
editCtrl.Focus()

; 3. 验证逻辑
VerifyPassword(*) {
    global password, myGui, editCtrl
    if (editCtrl.Value == password) {
        myGui.Destroy()
        ExitApp
    } else {
        editCtrl.Value := "" ; 清空错误密码
        editCtrl.Focus()    ; 重新聚焦，不弹窗，直接重输
    }
}

; 屏蔽系统按键
!f4::return
LWin::return
RWin::return

; 即使 GWS 切换导致失去焦点，点击屏幕也重新聚焦
~LButton::editCtrl.Focus()