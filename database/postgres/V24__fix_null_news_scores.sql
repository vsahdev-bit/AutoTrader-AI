-- Fix NULL news_sentiment_score and news_momentum_score values
-- These should default to 0.0 (neutral) when no news data is available

UPDATE stock_recommendations
SET news_sentiment_score = 0.0
WHERE news_sentiment_score IS NULL;

UPDATE stock_recommendations
SET news_momentum_score = 0.0
WHERE news_momentum_score IS NULL;

-- Also update big_cap_losers_recommendations if it has the same columns
UPDATE big_cap_losers_recommendations
SET news_sentiment_score = 0.0
WHERE news_sentiment_score IS NULL;

UPDATE big_cap_losers_recommendations
SET news_momentum_score = 0.0
WHERE news_momentum_score IS NULL;
