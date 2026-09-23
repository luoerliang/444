第16版基础改进版：fixed28

保留第16版的预测评分与回测命中率逻辑，不删已有数据库历史。
内置用户已提供的机器人历史作为首次启动种子；Telegram 新开奖优先级最高，收到后覆盖同一期种子数据，但不会删除其它历史。

Render：Build = pip install -r requirements.txt
Start = gunicorn app:app
环境变量：TELEGRAM_BOT_TOKEN（使用你原来的机器人 Token）

部署后：
/health 可查看 total、latest、telegram_configured。
网页每15秒刷新。
