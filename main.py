import os

def create_project_snapshot(root_dir, output_filename="project_snapshot.txt"):
    """
    تمام فایل‌های متنی در یک دایرکتوری و زیرشاخه‌های آن را می‌خواند
    و آن‌ها را در یک فایل txt واحد با فرمت مشخص شده ذخیره می‌کند.
    """
    
    # لیست پوشه‌ها و فایل‌هایی که باید نادیده گرفته شوند
    exclude_dirs = {'.git', 'node_modules', '__pycache__', 'venv', '.vscode', 'dist', 'build'}
    exclude_files = {output_filename, '.DS_Store', '.gitignore','package-lock.json','.env'}
    
    all_file_contents = []
    output_file_path = os.path.join(root_dir, output_filename)

    # os.walk به ما اجازه می‌دهد تا پوشه‌ها را به صورت بازگشتی بگردیم
    # topdown=True به ما اجازه می‌دهد لیست dirnames را در جا تغییر دهیم تا از ورود به پوشه‌های exclude شده جلوگیری کنیم
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
        
        # هرس کردن (Pruning) پوشه‌هایی که نمی‌خواهیم واردشان شویم
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        
        for filename in filenames:
            # نادیده گرفتن فایل‌های موجود در لیست exclude
            if filename in exclude_files:
                continue
                
            file_path = os.path.join(dirpath, filename)
            
            # دریافت آدرس نسبی فایل نسبت به فولدر ریشه
            # ما از / به عنوان جداکننده استفاده می‌کنیم تا با مثال شما مطابقت داشته باشد
            relative_path = os.path.relpath(file_path, root_dir).replace(os.sep, '/')
            
            try:
                # خواندن محتوای فایل با انکودینگ utf-8
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # اضافه کردن بلاک فرمت‌شده به لیست
                formatted_block = f"{relative_path}\n```\n{content}\n```\n\n"
                all_file_contents.append(formatted_block)
                
            except UnicodeDecodeError:
                # اگر فایل باینری بود یا انکودینگ دیگری داشت، آن را نادیده می‌گیریم
                print(f"فایل باینری یا غیر UTF-8 نادیده گرفته شد: {relative_path}")
            except Exception as e:
                print(f"خطا در خواندن فایل {relative_path}: {e}")

    # نوشتن کل محتوای جمع‌آوری شده در فایل خروجی
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write("".join(all_file_contents))
        print(f"\n✅ پروژه با موفقیت در فایل زیر ذخیره شد:")
        print(f"{output_file_path}")
    except Exception as e:
        print(f"\n❌ خطا در نوشتن فایل خروجی: {e}")

# --- اجرای اسکریپت ---
if __name__ == "__main__":
    # آدرس فولدر پروژه را از کاربر دریافت کن
    # می‌توانید به جای input، آدرس را مستقیماً اینجا بنویسید
    # مثلا: project_path = r"C:\Users\YourUser\Documents\MyProject"
    project_path = input("آدرس فولدر ریشه (پروژه) را وارد کنید: ")
    
    if os.path.isdir(project_path):
        create_project_snapshot(project_path)
    else:
        print("خطا: آدرس وارد شده یک فولدر معتبر نیست.")