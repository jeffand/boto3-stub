variable "aws_region" {
  description = "AWS region for the resources"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name for tagging"
  type        = string
  default     = "production"
}
