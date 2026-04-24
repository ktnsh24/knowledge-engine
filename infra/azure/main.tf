# Terraform — Azure infrastructure for knowledge-engine
# Resources: Azure OpenAI, Cosmos DB NoSQL, Azure AI Search, Storage Account
# Cost: ~€0 idle, ~€0.50-1.00 per 2hr run

terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }

  backend "azurerm" {
    resource_group_name  = "knowledge-engine-tfstate-rg"
    storage_account_name = "ketantfstate"
    container_name       = "tfstate"
    key                  = "knowledge-engine.terraform.tfstate"
  }
}

provider "azurerm" {
  features {}
}

variable "location" {
  default = "westeurope"
}

variable "environment" {
  default = "dev"
}

locals {
  prefix = "ke-${var.environment}"
  rg     = "${local.prefix}-rg"
}

resource "azurerm_resource_group" "main" {
  name     = local.rg
  location = var.location
  tags     = { Project = "knowledge-engine", Provider = "azure" }
}

# --- Azure OpenAI ---
resource "azurerm_cognitive_account" "openai" {
  name                = "${local.prefix}-openai"
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  kind                = "OpenAI"
  sku_name            = "S0"
  tags                = { Project = "knowledge-engine" }
}

resource "azurerm_cognitive_deployment" "gpt4o_mini" {
  name                 = "gpt-4o-mini"
  cognitive_account_id = azurerm_cognitive_account.openai.id
  model {
    format  = "OpenAI"
    name    = "gpt-4o-mini"
    version = "2024-07-18"
  }
  scale {
    type     = "Standard"
    capacity = 10  # 10K tokens/min — enough for dev
  }
}

resource "azurerm_cognitive_deployment" "embed" {
  name                 = "text-embedding-3-small"
  cognitive_account_id = azurerm_cognitive_account.openai.id
  model {
    format  = "OpenAI"
    name    = "text-embedding-3-small"
    version = "1"
  }
  scale {
    type     = "Standard"
    capacity = 10
  }
}

# --- Cosmos DB NoSQL (graph + vector store) ---
resource "azurerm_cosmosdb_account" "main" {
  name                = "${local.prefix}-cosmos"
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = var.location
    failover_priority = 0
  }

  # Free tier: 400 RU/s free per account
  enable_free_tier = true
  tags             = { Project = "knowledge-engine" }
}

resource "azurerm_cosmosdb_sql_database" "main" {
  name                = "knowledge-engine"
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
}

resource "azurerm_cosmosdb_sql_container" "topics" {
  name                = "topics"
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_path  = "/id"
  throughput          = 400
}

resource "azurerm_cosmosdb_sql_container" "edges" {
  name                = "edges"
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_path  = "/id"
  throughput          = 400
}

# --- Azure AI Search (vector store) ---
resource "azurerm_search_service" "main" {
  name                = "${local.prefix}-search"
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "free"  # Free tier: 50MB index, 3 indexes
  tags                = { Project = "knowledge-engine" }
}

# --- Storage: wiki backup ---
resource "azurerm_storage_account" "wiki" {
  name                     = "${replace(local.prefix, "-", "")}wiki"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  tags                     = { Project = "knowledge-engine" }
}

# --- Outputs ---
output "openai_endpoint" {
  value = azurerm_cognitive_account.openai.endpoint
}

output "cosmos_endpoint" {
  value = azurerm_cosmosdb_account.main.endpoint
}

output "search_endpoint" {
  value = "https://${azurerm_search_service.main.name}.search.windows.net"
}

output "resource_group" {
  value = azurerm_resource_group.main.name
}
