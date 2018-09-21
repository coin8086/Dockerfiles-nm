param (
  [Parameter(Mandatory=$true)]
  [Microsoft.Azure.Commands.Compute.Automation.Models.PSVirtualMachineScaleSet] $vmss
)

Add-AzureRmVmssExtension -VirtualMachineScaleSet $vmss -Name nodeagent1 -Publisher Microsoft.HpcPack -Type HpcAcmAgent -TypeHandlerVersion 1.0
Update-AzureRmVmss -VirtualMachineScaleSet $vmss -ResourceGroupName $vmss.ResourceGroupName -VMScaleSetName $vmss.Name
Update-AzureRmVmssInstance -ResourceGroupName $vmss.ResourceGroupName -VMScaleSetName $vmss.Name -InstanceId "*"

