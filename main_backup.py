# Background task for hourly data backup
async def periodic_backup():
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        # Full backup every hour
        await asyncio.sleep(3600)  # 1 hour
        
        try:
            from cogs.stats.gamification import cozy_gamification
            
            logging.info('🕐 HOURLY BACKUP: Starting complete data backup...')
            
            # Save voice time data for all servers
            if guild_voice_time:
                save_voice_time_data()
                logging.info('✅ Voice time data saved for all servers')
            
            # Save gamification data (users, points, achievements, etc.)
            cozy_gamification.save_user_data()
            logging.info('✅ Gamification data saved for all users')
            
            logging.info('✅ HOURLY BACKUP: Complete backup finished')
            
        except Exception as e:
            logging.error(f'❌ HOURLY BACKUP FAILED: {e}')
        
        # Save current stats for API
        save_current_stats_for_api()