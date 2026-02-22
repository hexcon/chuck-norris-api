variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-north-1" # Stockholm — closest to Estonia
}

variable "instance_type" {
  description = "EC2 instance type (t2.micro is free tier eligible)"
  type        = string
  default     = "t2.micro"
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH into the instance (your IP/32)"
  type        = string
}

variable "key_pair_name" {
  description = "Name of an existing EC2 key pair for SSH access"
  type        = string
}

variable "alert_email" {
  description = "Email address for CloudWatch alarm notifications"
  type        = string
}

variable "project_name" {
  description = "Project name used for tagging resources"
  type        = string
  default     = "chuck-norris-api"
}
