terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.2.0"
}

provider "aws" {
  region = var.aws_region
}

# Create SSM Automation Document
resource "aws_ssm_document" "capacity_reservation_automation" {
  name            = "CapacityReservationAutomation"
  document_type   = "Automation"
  document_format = "YAML"
  content         = file("${path.module}/../capacity_reservation_automation.yaml")

  tags = {
    Environment = var.environment
    Terraform   = "true"
  }
}
