import { useAuth } from '../../context/AuthContext';
import { User } from 'lucide-react';

const Header = ({ title }) => {
  const { user } = useAuth();

  return (
    <header className="bg-white border-b border-gray-200 px-8 py-4">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800">{title}</h2>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-gray-100 px-4 py-2 rounded-lg">
            <User size={20} className="text-gray-600" />
            <span className="text-sm font-medium text-gray-700">
              {user?.username || 'Admin'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
