澳门六合彩3分分析 fixed26

Render:
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
Environment Variable:
TELEGRAM_BOT_TOKEN=你的机器人Token

这版：
1. 只接收 Telegram 机器人开奖数据作为实时主源。
2. 已内置当前已提供的机器人历史种子（含去重后的58期，最新217期）。
3. 历史6个平码严格保持机器人原始顺序，只有预测22码按01-49升序。
4. 特码预测只使用历史特码评分；生肖预测独立计算，每个生肖最多2个号码。
5. 启动时自动建库、导入历史、启动 Telegram 长轮询，并清理旧 webhook（不丢待处理消息）。
6. /health 可检查服务是否运行。

注意：Render 免费实例可能休眠；手机熄屏不会直接停止服务器，但免费实例是否持续运行由 Render 平台决定。
