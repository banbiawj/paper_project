        document.addEventListener('DOMContentLoaded', function() {
            const menuToggle = document.querySelector('.menu-toggle');
            const sidebar = document.querySelector('.sidebar');
            const overlay = document.querySelector('.overlay');
            const closeSidebar = document.querySelector('.close-sidebar');
            
            // 移动端菜单切换
            if (menuToggle) {
                menuToggle.addEventListener('click', function() {
                    sidebar.classList.add('active');
                    overlay.classList.add('active');
                });
            }
            
            if (overlay) {
                overlay.addEventListener('click', function() {
                    sidebar.classList.remove('active');
                    overlay.classList.remove('active');
                });
            }
            
            if (closeSidebar) {
                closeSidebar.addEventListener('click', function() {
                    sidebar.classList.remove('active');
                    overlay.classList.remove('active');
                });
            }
            
            // 邮件卡片选择
            // const emailCards = document.querySelectorAll('.email-card');
            // emailCards.forEach(card => {
            //     card.addEventListener('click', function(e) {
            //         // 防止点击复选框时触发两次
            //         if (!e.target.classList.contains('form-check-input')) {
            //             const checkbox = this.querySelector('.form-check-input');
            //             checkbox.checked = !checkbox.checked;
            //             this.classList.toggle('selected', checkbox.checked);
            //         }
            //     });
            // });
            
            // 响应窗口大小变化
            window.addEventListener('resize', function() {
                if (window.innerWidth > 992) {
                    sidebar.classList.remove('active');
                    overlay.classList.remove('active');
                }
            });

            const toolbarContainer = document.querySelector('.toolbar-container');
            const scrollProgress = document.getElementById('scrollProgress');
            
            if (toolbarContainer && scrollProgress) {
                toolbarContainer.addEventListener('scroll', function() {
                const scrollWidth = toolbarContainer.scrollWidth - toolbarContainer.clientWidth;
                const scrollLeft = toolbarContainer.scrollLeft;
                const progress = (scrollLeft / scrollWidth) * 100;
                scrollProgress.style.width = progress + '%';
                });
            }


            // 悬浮按钮交互功能
            const mainBtn = document.getElementById('mainFloatingBtn');
            const btnMenu = document.getElementById('floatingBtnMenu');
            
            // 主按钮点击事件
            mainBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                btnMenu.classList.toggle('show');
                
                // 切换图标
                const icon = this.querySelector('i');
                if (btnMenu.classList.contains('show')) {
                    icon.classList.remove('bi-plus-lg');
                    icon.classList.add('bi-x');
                } else {
                    icon.classList.remove('bi-x');
                    icon.classList.add('bi-plus-lg');
                }
            });
            
            // 点击菜单项
            // document.querySelectorAll('.menu-item').forEach(item => {
            //     item.addEventListener('click', function(e) {
            //         e.preventDefault();
            //         const action = this.querySelector('span').textContent;
            //         alert(`执行: ${action}`);
            //         btnMenu.classList.remove('show');
                    
            //         // 恢复图标
            //         const icon = mainBtn.querySelector('i');
            //         icon.classList.remove('bi-x');
            //         icon.classList.add('bi-plus-lg');
            //     });
            // });
            
            // 点击页面其他地方关闭菜单
            document.addEventListener('click', function(e) {
                if (!mainBtn.contains(e.target) && !btnMenu.contains(e.target)) {
                    btnMenu.classList.remove('show');
                    
                    // 恢复图标
                    const icon = mainBtn.querySelector('i');
                    icon.classList.remove('bi-x');
                    icon.classList.add('bi-plus-lg');
                }
            });
            
            // 窗口大小变化时调整
            window.addEventListener('resize', function() {
                // 在小屏幕上自动关闭菜单
                if (window.innerWidth < 576) {
                    btnMenu.classList.remove('show');
                    
                    // 恢复图标
                    const icon = mainBtn.querySelector('i');
                    icon.classList.remove('bi-x');
                    icon.classList.add('bi-plus-lg');
                }
            });
        });

                