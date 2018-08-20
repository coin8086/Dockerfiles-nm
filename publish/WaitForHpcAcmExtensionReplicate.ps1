while (!(Get-AzureVMAvailableExtension -ExtensionName HpcAcmAgent -Publisher Microsoft.HpcPack).ReplicationCompleted) 
{
    $n = [System.DateTime]::Now
    echo "$n"
    sleep 5; 
}
