# ---------------------------------------------------------------------------
# SNS Topic for alerts
# ---------------------------------------------------------------------------
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
}

resource "aws_sns_topic_subscription" "email_alert" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "app_logs" {
  name              = "/app/${var.project_name}"
  retention_in_days = 30

  tags = {
    Name = "${var.project_name}-logs"
  }
}

# ---------------------------------------------------------------------------
# Metric Filters
# ---------------------------------------------------------------------------

# Auth failures (401/403 responses)
resource "aws_cloudwatch_log_metric_filter" "auth_failures" {
  name           = "${var.project_name}-auth-failures"
  log_group_name = aws_cloudwatch_log_group.app_logs.name
  pattern        = "{ $.event_type = \"auth_failure\" }"

  metric_transformation {
    name          = "AuthFailureCount"
    namespace     = var.project_name
    value         = "1"
    default_value = "0"
  }
}

# Brute force detection
resource "aws_cloudwatch_log_metric_filter" "brute_force" {
  name           = "${var.project_name}-brute-force"
  log_group_name = aws_cloudwatch_log_group.app_logs.name
  pattern        = "{ $.event_type = \"brute_force_detected\" }"

  metric_transformation {
    name          = "BruteForceCount"
    namespace     = var.project_name
    value         = "1"
    default_value = "0"
  }
}

# Server errors (5xx)
resource "aws_cloudwatch_log_metric_filter" "server_errors" {
  name           = "${var.project_name}-server-errors"
  log_group_name = aws_cloudwatch_log_group.app_logs.name
  pattern        = "{ $.event_type = \"server_error\" }"

  metric_transformation {
    name          = "ServerErrorCount"
    namespace     = var.project_name
    value         = "1"
    default_value = "0"
  }
}

# ---------------------------------------------------------------------------
# CloudWatch Alarms
# ---------------------------------------------------------------------------

# EC2 status check failure (instance health)
resource "aws_cloudwatch_metric_alarm" "instance_health" {
  alarm_name          = "${var.project_name}-instance-health"
  alarm_description   = "EC2 instance status check failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    InstanceId = aws_instance.app_server.id
  }
}

# Auth failure spike (potential attack)
resource "aws_cloudwatch_metric_alarm" "auth_failure_spike" {
  alarm_name          = "${var.project_name}-auth-failure-spike"
  alarm_description   = "High number of authentication failures — possible attack"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "AuthFailureCount"
  namespace           = var.project_name
  period              = 300
  statistic           = "Sum"
  threshold           = 20
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
}

# Brute force detected
resource "aws_cloudwatch_metric_alarm" "brute_force_alarm" {
  alarm_name          = "${var.project_name}-brute-force"
  alarm_description   = "Brute force attack detected by application"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BruteForceCount"
  namespace           = var.project_name
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
}

# Server error spike
resource "aws_cloudwatch_metric_alarm" "server_error_spike" {
  alarm_name          = "${var.project_name}-server-errors"
  alarm_description   = "High number of server errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ServerErrorCount"
  namespace           = var.project_name
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
}

# High CPU (might indicate crypto mining or DoS)
resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "${var.project_name}-high-cpu"
  alarm_description   = "CPU utilization exceeds 80% — possible DoS or compromise"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    InstanceId = aws_instance.app_server.id
  }
}
