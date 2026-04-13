export default function ChatInstance({ id, title }) {
    return (
        <a href={`/?id=${id}`} className="flex justify-center items-center 
            h-4 p-5 backdrop-brightness-200
            hover:backdrop-brightness-175
            rounded-[7px] align-middle
            ">
            <h4 className="truncate w-[12vw]">{`${title}`}</h4>
        </a>
    )
}