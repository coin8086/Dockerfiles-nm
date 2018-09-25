param (
  [Parameter(Mandatory=$true)]
  [string] $rg
)

$vms = Get-AzureRmVm -ResourceGroupName $rg
foreach ($vm in $vms)
{
  Write-Host "Fixing $vm.Name"
  try {
    Remove-AzureRmVMExtension -ResourceGroupName $rg -VMName $vm.Name -Name "HpcAcmAgent" -Force
    
  }
  catch {
    Write-Host "failed to remove $vm.Name"
  }
  Set-AzureRmVMExtension -Publisher "Microsoft.HpcPack" -ExtensionType "HpcAcmAgent" -ResourceGroupName $rg -TypeHandlerVersion 1.0 -VMName $vm.Name -Location $vm.Location -Name "HpcAcmAgent"
}

