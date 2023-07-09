avg_rate_hour_denied = 0.087
sd_rate_hour_denied = 0.064

avg_rate_hour_reversed = 0.004
sd_rate_hour_reversed = 0.005

avg_rate_hour_failed = 0.0001
sd_rate_hour_failed = 0.0002

z_score_threshold_denied = 3
z_score_threshold_reversed = 3
z_score_threshold_failed = 2

def z_score_hour_denied (num):
    return (num - avg_rate_hour_denied) / sd_rate_hour_denied

def z_score_hour_reversed (num):
    return (num - avg_rate_hour_reversed) / sd_rate_hour_reversed

def z_score_hour_failed (num):
    return (num - avg_rate_hour_failed) / sd_rate_hour_failed
