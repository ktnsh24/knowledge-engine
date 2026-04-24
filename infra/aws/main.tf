# Terraform — AWS infrastructure for knowledge-engine
# Resources: DynamoDB (vectors + graph), S3 (wiki backup), Bedrock (no resource needed — pay per call)
# Cost: ~€0 idle, ~€0.25-0.50 per 2hr run
# IMPORTANT: Always use personal AWS account (211132580210), never Odido account

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "knowledge-engine-tfstate-211132580210"
    key    = "knowledge-engine/terraform.tfstate"
    region = "eu-central-1"
  }
}

provider "aws" {
  region = var.aws_region

  # Safety: ensure we only ever touch the personal account
  allowed_account_ids = ["211132580210"]
}

variable "aws_region" {
  default = "eu-central-1"
}

variable "environment" {
  default = "dev"
}

locals {
  prefix = "knowledge-engine-${var.environment}"
}

# --- DynamoDB: Vector store ---
resource "aws_dynamodb_table" "vectors" {
  name         = "${local.prefix}-vectors"
  billing_mode = "PAY_PER_REQUEST"  # €0 idle cost
  hash_key     = "chunk_id"

  attribute {
    name = "chunk_id"
    type = "S"
  }

  tags = { Project = "knowledge-engine", Provider = "aws" }
}

# --- DynamoDB: Graph topics ---
resource "aws_dynamodb_table" "graph_topics" {
  name         = "${local.prefix}-graph-topics"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "topic_id"

  attribute {
    name = "topic_id"
    type = "S"
  }

  tags = { Project = "knowledge-engine", Provider = "aws" }
}

# --- DynamoDB: Graph edges ---
resource "aws_dynamodb_table" "graph_edges" {
  name         = "${local.prefix}-graph-edges"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "edge_id"

  attribute {
    name = "edge_id"
    type = "S"
  }

  # GSI for querying by source_id
  global_secondary_index {
    name            = "source_id-index"
    hash_key        = "source_id"
    projection_type = "ALL"
  }

  attribute {
    name = "source_id"
    type = "S"
  }

  tags = { Project = "knowledge-engine", Provider = "aws" }
}

# --- S3: Wiki output backup ---
resource "aws_s3_bucket" "wiki" {
  bucket = "${local.prefix}-wiki-${var.aws_region}"
  tags   = { Project = "knowledge-engine", Provider = "aws" }
}

resource "aws_s3_bucket_versioning" "wiki" {
  bucket = aws_s3_bucket.wiki.id
  versioning_configuration { status = "Enabled" }
}

# --- Budget alert: stop surprise bills ---
resource "aws_budgets_budget" "monthly" {
  name         = "${local.prefix}-monthly-budget"
  budget_type  = "COST"
  limit_amount = "5"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["ketan@personal.com"]
  }
}

output "vector_table_name" {
  value = aws_dynamodb_table.vectors.name
}

output "graph_topics_table_name" {
  value = aws_dynamodb_table.graph_topics.name
}

output "graph_edges_table_name" {
  value = aws_dynamodb_table.graph_edges.name
}

output "wiki_bucket_name" {
  value = aws_s3_bucket.wiki.bucket
}
