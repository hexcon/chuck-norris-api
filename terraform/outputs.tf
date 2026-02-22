output "instance_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.app_server.public_ip
}

output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.app_server.id
}

output "api_url" {
  description = "Base URL for the API"
  value       = "http://${aws_instance.app_server.public_ip}:8000"
}

output "api_docs_url" {
  description = "FastAPI auto-generated documentation"
  value       = "http://${aws_instance.app_server.public_ip}:8000/docs"
}

output "security_group_id" {
  description = "Security group ID"
  value       = aws_security_group.app_sg.id
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for application logs"
  value       = aws_cloudwatch_log_group.app_logs.name
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i ~/.ssh/${var.key_pair_name}.pem ubuntu@${aws_instance.app_server.public_ip}"
}
