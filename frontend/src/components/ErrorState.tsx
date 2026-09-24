interface Props {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export default function ErrorState({
  title = 'Не удалось загрузить данные',
  message = 'Проверьте подключение к backend или повторите попытку.',
  onRetry,
}: Props) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
      <div className="text-red-800 font-medium mb-1">{title}</div>
      <div className="text-sm text-red-700 mb-4">{message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 text-sm rounded bg-red-600 text-white hover:bg-red-700"
        >
          Повторить
        </button>
      )}
    </div>
  );
}