while (!(Get-AzureVMAvailableExtension -ExtensionName HpcAcmAgent -Publisher Microsoft.HpcPack).ReplicationCompleted) 
{
    [System.DateTime]::Now; 
    sleep 5; 
}
