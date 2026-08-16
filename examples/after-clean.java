@Service
public class SettlementJob {
    private static final String API_KEY = System.getenv("SETTLEMENT_API_KEY");
    private static final URI HOST = URI.create(System.getenv("SETTLEMENT_HOST"));

    void run() {
        // one pass, oldest first, stops at the first failure
        repo.findPending().forEach(this::settle);
    }
}
