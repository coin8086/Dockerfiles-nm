[CmdletBinding(SupportsShouldProcess = $true, DefaultParametersetName="Publish", ConfirmImpact = "High")]
Param
(
    # The file path of the configuration file for deploying the HPC Pack cluster in Microsoft Azure, please refer to the the file "Manual.rtf" which can be found in the same folder of this script.
    [Parameter(Mandatory=$true)]
    [String] $MediaLink,

    [Parameter(Mandatory=$true)]
    [String] $Version,

    [Parameter(Mandatory=$false, ParameterSetName="Internal")]
    [Switch] $Internal,

    [Parameter(Mandatory=$false)]
    [Switch] $MoonCake,

    [Parameter(Mandatory=$false, ParameterSetName="Publish")]
    [String[]] $Regions = @(),

    [Parameter(Mandatory=$false)]
    [Switch] $Force
)

$bodyxml = @"
<?xml version="1.0" encoding="utf-8"?>
<ExtensionImage xmlns="http://schemas.microsoft.com/windowsazure" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">   
  <ProviderNameSpace>Microsoft.HpcPack</ProviderNameSpace>
  <Type>HPCAcmAgentWin</Type>
  <!--Update this version for each new release-->
  <Version>{TheVMExtensionVersion}</Version>
  <Label>The HPC Azure Cluster Management node agent</Label>
  <HostingResources>VmRole</HostingResources>
  <!--Update this field with correct link where the extension is published.-->
  <MediaLink>{TheVMExtensionMediaLink}</MediaLink>
  <Endpoints/>
  <PublicConfigurationSchema/>
  <PrivateConfigurationSchema/>
  <Description>The node agent for HPC Azure Cluster Management is a VM extension used to install and configure a HPC cluster to be managed by the HPC ACM service.</Description>
  <LocalResources />
  <IsInternalExtension>{IsInternalPlaceholder}</IsInternalExtension>
  <Eula>http://go.microsoft.com/fwlink/?LinkID=507756</Eula>
  <PrivacyUri>http://go.microsoft.com/fwlink/?LinkID=507755</PrivacyUri>
  <HomepageUri>http://www.microsoft.com/hpc</HomepageUri>
  <IsJsonExtension>true</IsJsonExtension>
  <DisallowMajorVersionUpgrade>true</DisallowMajorVersionUpgrade>
  <SupportedOS>Windows</SupportedOS>
  <CompanyName>Microsoft</CompanyName>
  <Regions>{TheRegions}</Regions>
</ExtensionImage>
"@


$bodyxml = $bodyxml.Replace("{TheVMExtensionVersion}", $Version).Replace("{TheVMExtensionMediaLink}", $MediaLink)
if($Internal.IsPresent)
{
    $bodyxml = $bodyxml.Replace("{IsInternalPlaceholder}", "true")
}
else
{
    $bodyxml = $bodyxml.Replace("{IsInternalPlaceholder}", "false")
}

if($null -eq $Regions -or $Regions.Count -eq 0)
{
    $bodyxml = $bodyxml.Replace("<Regions>{TheRegions}</Regions>", "")
}
else
{
    $bodyxml = $bodyxml.Replace("{TheRegions}", ($Regions -join ";"))
}

if($MoonCake.IsPresent)
{
    $uri = "https://management.core.chinacloudapi.cn/5a08dd6d-4a18-4f07-bebb-aeaf6167e4d8/services/extensions?action=update"
}
else
{
    $uri = "https://management.core.windows.net/630763e2-8d65-4e0e-b2be-328808b2f120/services/extensions?action=update"
}
$bodyxml
$cert = Get-Item "Cert:\CurrentUser\My\66B77C31C37A0A4A4957335DF94E876E0C05F4F8"

if (-not $Force.IsPresent)
{
if(-not $PsCmdlet.ShouldProcess("Start to update the VM extension to $Version", "Continue to update the VM extension to $Version ?", "Confirm"))
{
    throw "Abort to update the VM extension to $Version."
}
}

Invoke-RestMethod -Method Put -Uri $uri -Certificate $cert -Headers @{'x-ms-version'='2014-12-01'} -Body $bodyxml -ContentType application/xml
