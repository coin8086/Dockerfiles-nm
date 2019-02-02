Param (
    [Parameter(Mandatory=$true)]
    [version] $version,
    [Parameter(Mandatory=$false)]
    [Switch] $unregister,
    [Parameter(Mandatory=$false)]
    [Switch] $skipinternal
)

if ($unregister.IsPresent)
{
        $prever = [Version]::new($version.Major, $version.Minor, $version.Build -2, $version.Revision)
        echo "Unregister the old extension $prever"
        .\UnregisterHPCAcmVMExtension.ps1 -Version $prever -Force

        sleep 10

        echo "Waiting replicate"
        .\WaitForHpcAcmExtensionReplicate.ps1
}

if (-not $skipinternal.IsPresent)
{
        echo "Make the new extension $version internal"
        .\UpdateHPCAcmVMExtension.ps1 -Version $version -Internal -Force

        sleep 10

        echo "Waiting replicate"
        .\WaitForHpcAcmExtensionReplicate.ps1
}

while ($true)
{
        try
        {
                echo "Make the new extension $version public on South Central US"
                .\UpdateHPCAcmVMExtension.ps1 -Version $version -Region ("South Central US") -Force
                break
        }
        catch
        {
                sleep 5
        }
}

while ($true)
{
        try
        {
                echo "Make the new extension $version public on South Central US, and East Asia"
                .\UpdateHPCAcmVMExtension.ps1 -Version $version -Region ("South Central US", "East Asia") -Force
                break
        }
        catch
        {
                sleep 5
        }
}

while ($true)
{
        try
        {
                echo "Make the new extension $version public on All regions"
                .\UpdateHPCAcmVMExtension.ps1 -Version $version -Force
                break
        }
        catch
        {
                sleep 5
        }
}

sleep 10

echo "Waiting replicate"
.\WaitForHpcAcmExtensionReplicate.ps1

