#!/bin/bash
# deploy.sh

# Добавить всё
git add .

# Сделать коммит с сообщением (можно спросить, но для 1 клика — авто)
git commit -m "Auto-commit: $(date +'%Y-%m-%d %H:%M')"

# Запушить в main (или master)
git push origin main

echo "✅ Успешно запушено в GitHub!"