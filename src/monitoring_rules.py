avg_rate_min_denied = 0.128
sd_rate_min_denied = 0.122

avg_rate_min_reversed = 0.047
sd_rate_min_reversed = 0.102

avg_rate_min_failed = 0.012
sd_rate_min_failed = 0.007

avg_rate_hour_denied = 0.116
sd_rate_hour_denied = 0.045

avg_rate_hour_reversed = 0.030
sd_rate_hour_reversed = 0.056

avg_rate_hour_failed = 0.002
sd_rate_hour_failed = 0.005

def z_score_min_denied (num):
    return (num - avg_rate_min_denied) / sd_rate_min_denied

def z_score_min_reversed (num):
    return (num - avg_rate_min_reversed) / sd_rate_min_reversed

def z_score_min_failed (num):
    return (num - avg_rate_min_failed) / sd_rate_min_failed

def z_score_hour_denied (num):
    return (num - avg_rate_hour_denied) / sd_rate_hour_denied

def z_score_hour_reversed (num):
    return (num - avg_rate_hour_reversed) / sd_rate_hour_reversed

def z_score_hour_failed (num):
    return (num - avg_rate_hour_failed) / sd_rate_hour_failed
