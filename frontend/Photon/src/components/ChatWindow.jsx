import React from 'react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';

const ChatWindow = () => {
  return (
    <div className="flex flex-col h-full bg-background relative">
      {/* Messages Area - Scrollable */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 lg:px-12 py-8 space-y-6 custom-scrollbar">
        <div className="max-w-3xl mx-auto w-full space-y-6 pb-4">
          <ChatMessage 
            sender="ai" 
            text={
              <>
                <p className="mb-3">নিউটনের দ্বিতীয় সূত্র অনুযায়ী, <span className="font-bold">বল = ভর × ত্বরণ</span> (F = ma)।</p>
                <p>সহজভাবে বললে, কোনো বস্তুর ওপর বল প্রয়োগ করলে তার গতির পরিবর্তন হয় এবং এই পরিবর্তনের হার প্রযুক্ত বলের সমানুপাতিক।</p>
              </>
            } 
          />
          <ChatMessage 
            sender="user" 
            text="এই সূত্রটা একটি সহজ উদাহরণ দিয়ে বুঝিয়ে দিন।" 
          />
           <ChatMessage 
            sender="ai" 
            text={
              <>
                <p className="mb-3">অবশ্যই! মনে করো তুমি একটি সুপারশপে শপিং কার্ট ঠেলছ।</p>
                <ul className="list-disc list-inside space-y-2 ml-1">
                  <li>কার্টটি যদি খালি থাকে (ভর কম), তবে অল্প ধাক্কা দিলেই (বল কম) সেটি দ্রুত চলবে (ত্বরণ বেশি)।</li>
                  <li>কিন্তু কার্টটি যদি ভারী বাজার দিয়ে ভর্তি থাকে (ভর বেশি), তবে একই জোরে ধাক্কা দিলেও সেটি ধীরে চলবে (ত্বরণ কম)।</li>
                </ul>
                <p className="mt-3">অর্থাৎ, একই ত্বরণ সৃষ্টি করতে ভারী বস্তুর ওপর বেশি বল প্রয়োগ করতে হয়।</p>
              </>
            } 
          />
        </div>
      </div>

      {/* Input Area - Sticky Bottom */}
      <div className="sticky bottom-0 w-full bg-background/80 backdrop-blur-sm pb-6 px-4 md:px-8 lg:px-12 pt-2">
         <div className="max-w-3xl mx-auto w-full shadow-lg rounded-2xl">
            <ChatInput />
         </div>
      </div>
    </div>
  );
};

export default ChatWindow;
