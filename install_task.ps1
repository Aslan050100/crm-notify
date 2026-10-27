# Регистрирует задачу в Планировщике Windows для текущего пользователя:
# каждый день в 11:00 и затем каждый час до 20:00. Если компьютер был выключен
# в 11:00 — задача выполнится, как только он включится (повторов не будет:
# сервис сам помнит, что за сегодня уже всё отправлено).
# Запуск: правой кнопкой по файлу → «Выполнить с помощью PowerShell».
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$action = New-ScheduledTaskAction -Execute "$dir\due.bat" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -Daily -At "11:00"
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At "11:00" -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Hours 9)).Repetition
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "crm-notify" -Action $action -Trigger $trigger -Settings $settings -Description "InsightIT crm-notify: поздравления с ДР из amoCRM через Wazzup" -Force | Out-Null
Write-Host "Готово: задача crm-notify зарегистрирована (Планировщик заданий → Библиотека планировщика → crm-notify)."
Read-Host "Нажмите Enter, чтобы закрыть"
