output "automation_document_name" {
  description = "Name of the created SSM Automation document"
  value       = aws_ssm_document.capacity_reservation_automation.name
}

output "automation_document_version" {
  description = "Version of the created SSM Automation document"
  value       = aws_ssm_document.capacity_reservation_automation.latest_version
}
