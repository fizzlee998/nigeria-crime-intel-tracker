import schedule
import time
from classify_and_save import run_pipeline

# Run every hour. Change the number to whatever interval you want.
schedule.every(1).hours.do(run_pipeline)

print("Scheduler started. Running pipeline now, then every 1 hour.")
print("Press CTRL+C to stop.\n")

# Run once immediately on startup, then wait for the schedule
run_pipeline()

while True:
    schedule.run_pending()
    time.sleep(60)