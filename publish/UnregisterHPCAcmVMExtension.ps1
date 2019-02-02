[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
Param
(
    [Parameter(Mandatory=$true)]
    [String] $Version,

    [Parameter(Mandatory=$false)]
    [Switch] $MoonCake,

    [Parameter(Mandatory=$false)]
    [Switch] $Force
) 

echo "Make the old extension $Version internal"
.\UpdateHPCAcmVMExtension.ps1 -Version $Version -Internal -Force
sleep 10

if($MoonCake.IsPresent)
{
    $uri = "https://management.core.chinacloudapi.cn/5a08dd6d-4a18-4f07-bebb-aeaf6167e4d8/services/extensions/Microsoft.HpcPack/HpcAcmAgent/$Version"
}
else
{
    $uri = "https://management.core.windows.net/630763e2-8d65-4e0e-b2be-328808b2f120/services/extensions/Microsoft.HpcPack/HpcAcmAgent/$Version"
}
$uri

if(-not $Force.IsPresent)
{
    if(-not $PsCmdlet.ShouldProcess("Start to unregister the VM extension $Version", "Continue to unregister the VM extension $Version ?", "Confirm"))
    {
        throw "The VM extension $Version unregister aborted"
    }
}

$cert = Get-Item "Cert:\CurrentUser\My\66B77C31C37A0A4A4957335DF94E876E0C05F4F8"
Invoke-RestMethod -Method Delete -Uri $uri -Certificate $cert -Headers @{'x-ms-version'='2014-12-01'} -ContentType application/xml 

