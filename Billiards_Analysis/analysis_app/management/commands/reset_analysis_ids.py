from django.core.management.base import BaseCommand
from django.db import connection
from analysis_app.models import BilliardAnalysis

class Command(BaseCommand):
    help = '重置 BilliardAnalysis 表的 ID 自增序列'

    def handle(self, *args, **options):
        # 获取当前数据库后端
        db_engine = connection.vendor
        
        with connection.cursor() as cursor:
            # 根据数据库类型执行不同的 SQL
            if db_engine == 'sqlite':
                # SQLite 重置自增序列方法
                # 先清空表
                self.stdout.write('正在清空 BilliardAnalysis 表...')
                BilliardAnalysis.objects.all().delete()
                self.stdout.write('表已清空。SQLite 会自动重置自增序列。')
                
            elif db_engine == 'postgresql':
                # PostgreSQL 重置序列方法
                table_name = BilliardAnalysis._meta.db_table
                sequence_name = f"{table_name}_id_seq"
                self.stdout.write(f'正在重置 PostgreSQL 序列 {sequence_name}...')
                cursor.execute(f"ALTER SEQUENCE {sequence_name} RESTART WITH 1;")
                self.stdout.write('序列已重置。')
                
            elif db_engine == 'mysql':
                # MySQL 重置自增序列方法
                table_name = BilliardAnalysis._meta.db_table
                self.stdout.write(f'正在重置 MySQL 表 {table_name} 自增计数器...')
                cursor.execute(f"ALTER TABLE {table_name} AUTO_INCREMENT = 1;")
                self.stdout.write('自增计数器已重置。')
                
            else:
                self.stdout.write(self.style.WARNING(f'不支持的数据库类型: {db_engine}'))
                return
        
        self.stdout.write(self.style.SUCCESS('BilliardAnalysis ID 重置成功!'))
