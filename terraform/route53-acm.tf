# Look up the existing Route 53 hosted zone for solola.net
data "aws_route53_zone" "solola" {
  name         = "solola.net."
  private_zone = false
}

# ACM certificate for solola.net (must be in us-east-1 for CloudFront)
resource "aws_acm_certificate" "solola" {
  domain_name               = "solola.net"
  subject_alternative_names = ["www.solola.net"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name    = "solola.net"
    Project = "eg-solo"
  }
}

# Route 53 DNS validation records for ACM
resource "aws_route53_record" "solola_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.solola.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.solola.zone_id
}

# Wait for certificate validation to complete
resource "aws_acm_certificate_validation" "solola" {
  certificate_arn         = aws_acm_certificate.solola.arn
  validation_record_fqdns = [for record in aws_route53_record.solola_cert_validation : record.fqdn]
}

# Route 53 A record for solola.net -> CloudFront
resource "aws_route53_record" "solola_apex" {
  zone_id = data.aws_route53_zone.solola.zone_id
  name    = "solola.net"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}

# Route 53 A record for www.solola.net -> CloudFront
resource "aws_route53_record" "solola_www" {
  zone_id = data.aws_route53_zone.solola.zone_id
  name    = "www.solola.net"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}
