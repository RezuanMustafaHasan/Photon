import React from 'react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';

const ChatWindow = () => {
  return (
    <div className="d-flex flex-column h-100 bg-background position-relative">
      {/* Messages Area - Scrollable */}
      <div className="flex-grow-1 overflow-y-auto px-4 px-md-5 px-lg-5 py-4 vstack gap-4 custom-scrollbar">
        <div className="container-sm mw-100 vstack gap-4 pb-4" style={{ maxWidth: '48rem' }}>
          <ChatMessage 
            sender="ai" 
            text={
              <>
                <p className="mb-3">নিউটনের দ্বিতীয় সূত্র অনুযায়ী, <span className="fw-bold">বল = ভর × ত্বরণ</span> (F = ma)।</p>
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
                <ul className="list-disc list-inside vstack gap-2 ms-1">
                  <li>কার্টটি যদি খালি থাকে (ভর কম), তবে অল্প ধাক্কা দিলেই (বল কম) সেটি দ্রুত চলবে (ত্বরণ বেশি)।</li>
                  <li>কিন্তু কার্টটি যদি ভারী বাজার দিয়ে ভর্তি থাকে (ভর বেশি), তবে একই জোরে ধাক্কা দিলেও সেটি ধীরে চলবে (ত্বরণ কম)।</li>
                </ul>
                <p className="mt-3">অর্থাৎ, একই ত্বরণ সৃষ্টি করতে ভারী বস্তুর ওপর বেশি বল প্রয়োগ করতে হয়।</p>
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
                <ul className="list-disc list-inside vstack gap-2 ms-1">
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
      <div className="sticky-bottom w-100 backdrop-blur-sm pb-4 px-4 px-md-5 px-lg-5 pt-2">
         <div className="container-sm mw-100 shadow-lg rounded-2xl bg-white" style={{ maxWidth: '48rem' }}>
            <ChatInput />
         </div>
      </div>
    </div>
  );
};

export default ChatWindow;
