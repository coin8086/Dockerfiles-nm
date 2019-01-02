while (!(Get-AzureVMAvailableExtension -ExtensionName HpcAcmAgentWin -Publisher Microsoft.HpcPack).ReplicationCompleted) 
{
    $n = [System.DateTime]::Now
    echo "$n"
    sleep 5; 
}
