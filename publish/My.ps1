function Remove-MyVMExtension {
    Param (
        [Parameter(Mandatory=$true)]
        [string] $type,
        [Parameter(Mandatory=$true)]
        [string] $version
    )

    $url = "https://management.core.windows.net/630763e2-8d65-4e0e-b2be-328808b2f120/services/extensions/Microsoft.HpcPack/$type/$version"
    $cert = Get-Item "Cert:\CurrentUser\My\66B77C31C37A0A4A4957335DF94E876E0C05F4F8"
    Invoke-RestMethod -Method Delete -Uri $url -Certificate $cert -Headers @{'x-ms-version'='2014-12-01'}
}

function Update-MyVMExtension {
    Param (
        [Parameter(Mandatory=$true)]
        [string] $type,

        [Parameter(Mandatory=$true)]
        [string] $version,

        [Parameter(Mandatory=$true)]
        [string] $packageUrl,

        [string] $description,

        [String[]] $regions = @(),

        [switch] $internal,

        [switch] $create
    )

    if (!$description -and $internal) {
        $description = 'The VM Extension is for internal use only.'
    }
    $regions = $regions -join ";"

    $definition = @"
<?xml version="1.0" encoding="utf-8"?>
<ExtensionImage xmlns="http://schemas.microsoft.com/windowsazure" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
  <ProviderNameSpace>Microsoft.HpcPack</ProviderNameSpace>
  <Type>$type</Type>
  <Version>$version</Version>
  <Label>The HPC Azure Cluster Management node agent</Label>
  <HostingResources>VmRole</HostingResources>
  <MediaLink>$packageUrl</MediaLink>
  <Endpoints/>
  <PublicConfigurationSchema/>
  <PrivateConfigurationSchema/>
  <Description>$description</Description>
  <LocalResources />
  <IsInternalExtension>$internal</IsInternalExtension>
  <Eula>http://go.microsoft.com/fwlink/?LinkID=507756</Eula>
  <PrivacyUri>http://go.microsoft.com/fwlink/?LinkID=507755</PrivacyUri>
  <HomepageUri>http://www.microsoft.com/hpc</HomepageUri>
  <IsJsonExtension>true</IsJsonExtension>
  <DisallowMajorVersionUpgrade>true</DisallowMajorVersionUpgrade>
  <SupportedOS>Linux</SupportedOS>
  <CompanyName>Microsoft</CompanyName>
  <Regions>$regions</Regions>
</ExtensionImage>
"@

    $definition | Out-default

    $cert = Get-Item "Cert:\CurrentUser\My\66B77C31C37A0A4A4957335DF94E876E0C05F4F8"

    if ($create) {
        $url = "https://management.core.windows.net/630763e2-8d65-4e0e-b2be-328808b2f120/services/extensions"
        $method = 'Post'
    }
    else {
        $url = "https://management.core.windows.net/630763e2-8d65-4e0e-b2be-328808b2f120/services/extensions?action=update"
        $method = 'Put'
    }
    Invoke-RestMethod -Method $method -Uri $url -Certificate $cert -Headers @{'x-ms-version'='2014-12-01'} -Body $definition -ContentType application/xml
}

function Get-MyVMExtensions {
    $url = 'https://management.core.windows.net/630763e2-8d65-4e0e-b2be-328808b2f120/services/publisherextensions'
    $cert = Get-Item "Cert:\CurrentUser\My\66B77C31C37A0A4A4957335DF94E876E0C05F4F8"
    $r = Invoke-RestMethod -Method Get -Uri $url -Certificate $cert -Headers @{'x-ms-version'='2014-12-01'}
    $r.ExtensionImages.ExtensionImage
}

function Wait-MyVMExtension {
    Param (
        [Parameter(Mandatory=$true)]
        [string] $type,
        [Parameter(Mandatory=$true)]
        [string] $version,
        [Parameter(Mandatory=$false)]
        [int] $timeout
    )

    $start = Get-Date
    while ($true) {
        $exts = Get-MyVMExtensions
        foreach ($ext in $exts) {
            if ($ext.Type -eq $type -and $ext.Version -eq $version -and $ext.ReplicationCompleted -eq $true) {
                return $ext
            }
        }
        if ($timeout) {
            $elapsed = ($(Get-Date) - $start).TotalSeconds
            if ($elapsed -ge $timeout) {
              return
            }
        }
        Start-Sleep 10
    }
}
