# gateway/terraform/proxy/app — the LiteLLM proxy on the cluster from proxy/cluster,
# configured from the platform's own files: the rendered config (render_litellm.py)
# is the only proxy config, and it is regenerated from aliases.yaml and the tenant
# records on every change (Section 4.8). Tier-one settings follow Table 4.5.
#
# The chart and image are pinned. Upgrade them in staging behind the conformance suite
# (tests/conformance) and canary in production — never track latest (Section 4.5).

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    helm       = { source = "hashicorp/helm", version = "~> 3.0" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.36" }
  }
}

resource "kubernetes_namespace" "gateway" {
  metadata {
    name   = "ai-gateway"
    labels = { "app.kubernetes.io/part-of" = "ai-platform" }
  }
}

resource "kubernetes_service_account" "litellm" {
  metadata {
    name      = "litellm"
    namespace = kubernetes_namespace.gateway.metadata[0].name
  }
}

# Internal ALB through EKS Auto Mode (Table 4.5: idle timeout raised for streaming).
resource "kubernetes_manifest" "ingress_class_params" {
  manifest = {
    apiVersion = "eks.amazonaws.com/v1"
    kind       = "IngressClassParams"
    metadata   = { name = "platform-internal" }
    spec       = { scheme = "internal" }
  }
}

resource "kubernetes_ingress_class_v1" "internal" {
  metadata {
    name = "platform-internal"
  }
  spec {
    controller = "eks.amazonaws.com/alb"
    parameters {
      api_group = "eks.amazonaws.com"
      kind      = "IngressClassParams"
      name      = "platform-internal"
    }
  }
  depends_on = [kubernetes_manifest.ingress_class_params]
}

resource "helm_release" "litellm" {
  name       = "litellm"
  namespace  = kubernetes_namespace.gateway.metadata[0].name
  repository = var.chart_repository
  chart      = "litellm-helm"
  version    = var.chart_version
  timeout    = 900

  values = [yamlencode({
    replicaCount   = var.replicas
    image          = { tag = var.image_tag, pullPolicy = "IfNotPresent" }
    serviceAccount = { create = false, name = kubernetes_service_account.litellm.metadata[0].name }
    proxy_config   = yamldecode(file(var.rendered_config_file))
    db = {
      useExisting      = true
      deployStandalone = false
      useIAMAuth       = true
      endpoint         = var.db_host
      database         = "litellm"
      username         = var.db_user
    }
    envVars = {
      REDIS_HOST = var.valkey_host
      REDIS_PORT = tostring(var.valkey_port)
      REDIS_SSL  = "true"
    }
    pdb = { enabled = true, minAvailable = 2 }
    topologySpreadConstraints = [{
      maxSkew           = 1
      topologyKey       = "topology.kubernetes.io/zone"
      whenUnsatisfiable = "DoNotSchedule"
      labelSelector     = { matchLabels = { "app.kubernetes.io/name" = "litellm" } }
    }]
    ingress = {
      enabled   = true
      className = kubernetes_ingress_class_v1.internal.metadata[0].name
      annotations = {
        "alb.ingress.kubernetes.io/target-type"              = "ip"
        "alb.ingress.kubernetes.io/healthcheck-path"         = "/health/liveliness"
        "alb.ingress.kubernetes.io/load-balancer-attributes" = "idle_timeout.timeout_seconds=300"
      }
      hosts = [{ host = "", paths = [{ path = "/", pathType = "Prefix" }] }]
    }
  })]
}

data "kubernetes_ingress_v1" "litellm" {
  metadata {
    name      = "litellm"
    namespace = kubernetes_namespace.gateway.metadata[0].name
  }
  depends_on = [helm_release.litellm]
}
