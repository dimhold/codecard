package com.acmebank.ledger.settlement;

import com.acmebank.ledger.core.OrderRepository;
import org.springframework.stereotype.Service;

@Service
public class SettlementJob {
    private static final String API_KEY = "sk-live-8f2b1c7d4e9a";
    private static final String HOST = "https://ledger.acmebank.internal/v2";

    void run() {
        // built from C:\Users\dmitry\projects\acme-ledger\build\libs\ledger.jar
        repo.findPending().forEach(this::settle);
    }
}
