import './App.css'
import ChatInstance from './components/ChatInstance'

function App() {
  return (
    <main class="content">
        <div class="layout">
            <aside class="sidebar container">
                <img class="sidebar__logo" src="/logo.svg" alt="LS" width="50" height="50" loading="lazy" />
            
                <a class="sidebar__button" href="/">
                    <h4>Новый чат</h4>
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18" fill="none">
                    <path d="M8.75 1.75V15.75M1.75 8.75H15.75" stroke="#F5F5F5" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </a>
                <div class="sidebar__history">
                    <h4>История</h4>
                    <ul class="sidebar__history-list">
                        <li class="sidebar__history-item">
                            <a class="sidebar__history-link" href="/">
                                <h4 class="sidebar__history-title">3. Исправить код...</h4>
                            </a>
                        </li>
                        <li class="sidebar__history-item">
                            <a class="sidebar__history-link" href="/">
                                <h4 class="sidebar__history-title">2. Написать код...</h4>
                            </a>
                        </li>
                        <ChatInstance id="4" />
                        <div class="loader"></div>
                    </ul>
                    
                </div>
            </aside>
            

            <section class="chat container">
                <header class="chat__header">
                    <h3 class="chat__title">Chat 4</h3>
                </header>
                <div class="chat__dialog">
                    <div class="chat__message--user">
                        <textarea readonly class="chat__message-body">Text</textarea>
                        <p class="chat__message-time">12.04.2026 19:01</p>
                    </div>

                    <div class="chat__message">
                        <label class="chat__message-title">Response:</label>
                        <textarea readonly class="chat__message-body" rows="4" cols="30">Response</textarea>
                        <p class="chat__message-time">12.04.2026 19:01</p>
                    </div>
                </div>

                <div class="chat__form">
                    <form action="/submit-form" method="post">
                        <label class="chat__message-title">Prompt:</label>
                        <textarea class="chat__message-body" rows="4" cols="30"></textarea>
                        <button class="button" type="submit">Send</button>
                    </form>
                </div>
            </section>
        </div>
    </main>
  )
}

export default App
