export function TelegramIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      width={24}
      height={24}
      {...props}
    >
      <path
        fill="#26a5e4"
        d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0Z"
      />
      <path
        fill="#fff"
        d="M17.562 7.161c.18-.738-.449-1.032-1.075-.794L5.66 10.542c-.739.296-.728.707-.133.889l2.779.867 6.436-4.061c.304-.185.582-.085.354.118l-5.215 4.708-.203 3.028c.298 0 .43-.136.597-.297l1.433-1.394 2.981 2.201c.55.303.945.148 1.082-.509l1.791-8.931Z"
      />
    </svg>
  );
}
