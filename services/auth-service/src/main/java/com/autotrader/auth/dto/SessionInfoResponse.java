package com.autotrader.auth.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SessionInfoResponse {
    private UUID userId;
    private boolean authenticated;
    private boolean brokerageConnected;
    private LocalDateTime brokerageTokenExpiresAt;
}
