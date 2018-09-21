param (
  [Parameter(Mandatory=$true)]
  [Microsoft.Azure.Commands.Compute.Automation.Models.PSVirtualMachineScaleSet] $vmss
)

Remove-AzureRmVmssExtension -VirtualMachineScaleSet $vmss -Name nodeagent1
Update-AzureRmVmss -VirtualMachineScaleSet $vmss -ResourceGroupName $vmss.ResourceGroupName -VMScaleSetName $vmss.Name
Update-AzureRmVmssInstance -ResourceGroupName $vmss.ResourceGroupName -VMScaleSetName $vmss.Name -InstanceId "*"

