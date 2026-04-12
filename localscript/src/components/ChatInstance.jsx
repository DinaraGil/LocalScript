export default function ChatInstance({ id }) {
    return (
        <div class="sidebar__history-item">
            <a href={`/?id=${id}`}>
                <h4 class="sidebar__history-title">{`${id}`} hello</h4>
            </a>
        </div>
    )
}