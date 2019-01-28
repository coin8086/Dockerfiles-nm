Param (
    [Parameter(Mandatory=$true)]
    [version] $version,
    [Parameter(Mandatory=$false)]
    [Switch] $unregister
)

if ($unregister.IsPresent)
{
        $prever = [Version]::new($version.Major, $version.Minor, $version.Build -2, $version.Revision)
        echo $prever

        echo "Make the old extension $prever internal"
        .\UpdateHPCAcmVMExtension.ps1 -MediaLink https://evanc.blob.core.windows.net/linuxnm/HpcAcmAgent-$prever.zip -Version $prever -Internal -Force

        sleep 10

        echo "Unregister the old extension $prever"
        .\UnregisterHPCAcmVMExtension.ps1 -Version $prever -Force

        sleep 10

        echo "Waiting replicate"
        .\WaitForHpcAcmExtensionReplicate.ps1
}

echo "Make the new extension $version internal"
.\UpdateHPCAcmVMExtension.ps1 -MediaLink https://evanc.blob.core.windows.net/linuxnm/HpcAcmAgent-$version.zip -Version $version -Internal -Force

sleep 10

echo "Waiting replicate"
.\WaitForHpcAcmExtensionReplicate.ps1

while ($true)
{
        try
        {
                echo "Make the new extension $version public on South Central US"
                .\UpdateHPCAcmVMExtension.ps1 -MediaLink https://evanc.blob.core.windows.net/linuxnm/HpcAcmAgent-$version.zip -Version $version -Region ("South Central US") -Force
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
.\UpdateHPCAcmVMExtension.ps1 -MediaLink https://evanc.blob.core.windows.net/linuxnm/HpcAcmAgent-$version.zip -Version $version -Region ("South Central US", "East Asia") -Force
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
                .\UpdateHPCAcmVMExtension.ps1 -MediaLink https://evanc.blob.core.windows.net/linuxnm/HpcAcmAgent-$version.zip -Version $version -Force
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

