Param (
    [string] $action
)

function Log {
    param (
        [Parameter()]
        [string] $message,
        [string] $severity = "info"
    )
    
    Write-Verbose $message
    switch ($severity) {
        "info" { Write-Output $message }
        "warn" { Write-Warning $message }
        "error" { Write-Error $message }
    }
}

Log "====> Doing action $action"
switch ($action)
{
    "install" {
        Log "Installing msi"
        msiexec.exe /i HpcNodeAgent_x64.msi ADDLOCAL=NodeAgent CCPDIR=`"$env:ProgramFiles\Microsoft HPC Pack ACM\`" DATADIR=`"$env:ProgramFiles\Microsoft HPC Pack ACM\Data\`"

        Log "Installing winagent"
        Remove-Item -Path "$env:ProgramFiles\winagent" -Recurse -Force -ErrorAction Ignore
        Copy-Item -Path winagent -Destination "$env:ProgramFiles\" -Recurse -Force
        $configPath = "$env:ProgramFiles\winagent\appsettings.json"
        $config = Get-Content $configPath -Raw | ConvertFrom-Json
        $config.NodeRegisterWorkerOptions | Add-Member -Name "Enabled" -Value "True" -MemberType NoteProperty
        $config | ConvertTo-Json | Set-Content $configPath
    }
    "uninstall" {
        .\handler.ps1 "disable"
        Log "Uninstalling msi"
        $app = Get-WmiObject -Class Win32_Product -Filter "Name = 'Microsoft (R) HPC Pack 2016 ACM Agent'"
        if ($null -ne $app) { $app.Uninstall() }
        
        Log "Removing winagent"
        Remove-Item -Path "$env:ProgramFiles\winagent" -Recurse -Force -ErrorAction Ignore
    }
    "enable" {
        Log "Starting HpcNodeAgent"
        sc.exe start HpcNodeAgent
    }
    "disable" {
        Log "Stopping HpcNodeAgent"
        sc.exe stop HpcNodeAgent
    }
    "update" {

    }
    default { Log "Unknow action" }
}

Log "====> Done action $action"
